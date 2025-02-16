import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
from lib import generate_chessboard, format_chessboard, border, board_to_fen, get_coordinates, convert_coordinate
from stockfish import Stockfish

#Load environment variables from .env
load_dotenv()

#Define intents
intents = discord.Intents.default()
intents.message_content = True  #Makes the bot able to read messages
current_turn = 'w'

#Initialize bot with a command prefix
bot = commands.Bot(command_prefix="!", intents=intents)

stockfish = Stockfish(path=r"C:\stockfish\stockfish-windows-x86-64-avx2.exe", depth=18, parameters={"Threads": 2, "Minimum Thinking Time": 30})

#Event: Bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('-'*53)
    #Load emojis from your server
    guild_id = int(os.getenv("SERVER_ID")) #Get the server ID from dotenv file as a integer
    bot.chess_emojis = {}
    guild = bot.get_guild(guild_id)
    
    if guild:
        for emoji in guild.emojis:
            bot.chess_emojis[emoji.name] = f"<:{emoji.name}:{emoji.id}>"
    else:
        print("Error: Server not found!")

@bot.command()
async def chessboard(ctx):
    #Display chessboard using server emojis
    try:
        #Generate board structure
        board_state = generate_chessboard()
        #Format with emoji IDs
        formatted = format_chessboard(board_state, ctx.bot.chess_emojis)
        await ctx.send(formatted)
    except Exception as e:
        await ctx.send(f"Error: {e}\nMissing emojis? Use !emojicheck")
        print(f"Error: {e}")

@bot.command()
async def emojicheck(ctx):
    #Verify all required emojis exist
    board_state = generate_chessboard()
    required = {cell for row in board_state for cell in row}
    missing = [name for name in required if name not in ctx.bot.chess_emojis]
    
    if missing:
        await ctx.send(f"Missing emojis:\n{', '.join(missing)}")
    else:
        await ctx.send("All emojis are available!")

#Global board state storage
current_board = None
initial_board = generate_chessboard()

@bot.command()
async def move(ctx, source: str, destination: str):
    global current_board, current_turn
    
    try:
        await ctx.message.delete()
        
        if current_board is None:
            current_board = [row.copy() for row in initial_board]
            current_turn = 'w'

        #Convert player input
        src_col = source[0].lower()
        src_rank = int(source[1])
        dest_col = destination[0].lower()
        dest_rank = int(destination[1])

        #Validate move belongs to current player
        src_r, src_c = convert_coordinate(src_col, src_rank)
        piece = current_board[src_r][src_c].split('wbg')[0].split('bbg')[0]
        if current_turn == 'w' and not piece.startswith('w'):
            raise ValueError("Not your turn (white's move)")
        if current_turn == 'b' and not piece.startswith('b'):
            raise ValueError("Not your turn (black's move)")

        #Perform player move
        current_board = move_piece(src_col, src_rank, dest_col, dest_rank, current_board)
        current_turn = 'b' if current_turn == 'w' else 'w'
        
        #Update board display
        await update_board(ctx)
        
        #Stockfish move
        if current_turn == 'b':
            fen = board_to_fen(current_board, current_turn)
            stockfish.set_fen_position(fen)
            best_move = stockfish.get_best_move()
            
            if best_move:
                #Convert Stockfish move
                (sc_sf, sr_sf), (dc_sf, dr_sf) = get_coordinates(best_move)
                current_board = move_piece(sc_sf, sr_sf, dc_sf, dr_sf, current_board)
                current_turn = 'w'
                await update_board(ctx)

    except Exception as e:
        error_msg = await ctx.send(f"🚫 Error: {e}", delete_after=10)
        await asyncio.sleep(10)
        await error_msg.delete()

async def update_board(ctx):
    #Helper function to update the board display
    if hasattr(bot, 'board_messages'):
        from lib import format_chessboard, border
        new_lines = format_chessboard(current_board, bot.chess_emojis, border).split('\n')
        
        for i, (msg_id, old_line) in enumerate(bot.board_messages):
            if new_lines[i] != old_line:
                channel = bot.get_channel(ctx.channel.id)
                msg = await channel.fetch_message(msg_id)
                await msg.edit(content=new_lines[i])
                bot.board_messages[i] = (msg_id, new_lines[i])

@bot.command()
async def chesslines(ctx):
    #Send/update the chessboard with borders
    global current_board
    from lib import format_chessboard, border, generate_chessboard
    
    #Initialize board if needed
    if current_board is None:
        current_board = generate_chessboard()
    
    #Store message IDs and content
    formatted = format_chessboard(current_board, bot.chess_emojis, border)
    lines = formatted.split('\n')
    
    #Delete old messages if they exist
    if hasattr(bot, 'board_messages'):
        try:
            channel = bot.get_channel(ctx.channel.id)
            for msg_id, _ in bot.board_messages:
                msg = await channel.fetch_message(msg_id)
                await msg.delete()
        except:
            pass
    
    #Send new messages and store IDs
    bot.board_messages = []
    for line in lines:
        msg = await ctx.send(line)
        bot.board_messages.append((msg.id, line))

@bot.command()
async def debug(ctx):
    #Show current FEN and turn
    if current_board is not None:
        fen = board_to_fen(current_board, current_turn)
        await ctx.send(f"```FEN: {fen}\nTurn: {current_turn}```")
    else:
        await ctx.send("Board not initialized!")

@bot.command()
async def showraw(ctx):
    #Show raw board data
    if current_board:
        output = "Current Board:\n" + "\n".join([str(row) for row in current_board])
        await ctx.send(f"```{output}```")

@bot.command()
async def newgame(ctx):
    #Start a new chess game
    global current_board, current_turn
    current_board = None
    current_turn = 'w'
    await ctx.message.delete()
    await chesslines(ctx)

#Run the bot with a discord token
bot.run(os.getenv("DISCORD_TOKEN")) 