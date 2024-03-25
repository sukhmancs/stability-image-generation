# send images to a Discord channel
import base64
import requests
import os
import discord
from dotenv import load_dotenv
import os
import io
import asyncio
import time
import aiohttp
from aiohttp import FormData
from PIL import Image

# Load the .env file
load_dotenv()

# Get the tokens
stability_token = os.getenv('STABILITY_TOKEN')
discord_token = os.getenv('DISCORD_TOKEN')

class MyClient(discord.Client):
    """Class to represent the Client (bot user)"""

    def __init__(self):
        """This is the constructor. Sets the default 'intents' for the bot."""
        intents = discord.Intents.default()
        intents.message_content = True        
        super().__init__(intents=intents)

    async def on_ready(self):
        """Called when the bot is fully logged in."""
        print('Logged on as', self.user)

    async def on_message(self, message):
        """Called whenever the bot receives a message. The 'message' object
        contains all the pertinent information."""

        # don't respond to ourselves
        if message.author == self.user:
            return

        # provide help
        if message.content == '!help':
            await message.channel.send('To generate an image, type "!style_preset,negative_prompt,positive_prompt,cfg_scale,samples". For example: "!anime,blurry,A painting of a cat,5,1"')
            return
        
        # check message content and respond accordingly
        # generate image
        if message.content.startswith('!'):
            # split the message content
            message.content = message.content[1:]
            parts = message.content.split(',')

            # show the warning message if the message is not in the correct format
            if len(parts) != 5:
                await message.channel.send('Please provide the correct format. Type "!help" for more information.')
                return                
            else:                
                style_preset = parts[0] # anime, art, etc.
                negative_prompt = parts[1] # bad, blurry, etc.
                positive_prompt = parts[2] # good, sharp, etc.
                cfg_scale = parts[3] # 1, 2, 3, 4, 5
                samples = parts[4] # 1, 2, 3, 4, 5

            body = {
                "steps": 40,
                "width": 1024,
                "height": 1024,
                "seed": 0,
                "cfg_scale": int(cfg_scale),
                "samples": int(samples),
                "style_preset": style_preset,
                "text_prompts": [
                    {
                        "text": positive_prompt,
                        "weight": 1
                    },
                    {
                        "text": negative_prompt,
                        "weight": -1
                    }
                ],
            }
            # countdown
            default_message = await message.channel.send("Generating image...")
            countdown_message = await message.channel.send("7")
            for i in range(6, 0, -1):
                await countdown_message.edit(content=str(i))
                await asyncio.sleep(1)
                
                # delete the countdown message
                if i == 1:
                    await countdown_message.delete()
                    await default_message.edit(content="Image will be sent shortly...")

            start_time = time.time() # start the timer

            response = requests.post(
                url,
                headers=headers,
                json=body,
            )

            end_time = time.time() # end the timer

            time_elapsed = end_time - start_time

            if response.status_code != 200:
                raise Exception("Non-200 response: " + str(response.text))

            data = response.json()                      
            
            for i, image in enumerate(data["artifacts"]):
                image_bytes = base64.b64decode(image["base64"])
                image_file = io.BytesIO(image_bytes)
                image_file.name = f'txt2img_{image["seed"]}.png'                 
                await message.channel.send(file=discord.File(image_file))
            
            await default_message.delete() # delete the default message         
            await message.channel.send(f"Time elapsed: {time_elapsed:.2f} seconds")   

    
    async def on_reaction_add(self, reaction, user):
        """Called whenever a reaction is added to a message."""
        if user == self.user:
            return
        
        # don't respond to reactions that are not on images
        if not reaction.message.attachments:
            return
        
         # check if the reaction is the magnifying glass emoji
        if str(reaction.emoji) == '🔍':
            await reaction.message.channel.send('You clicked the magnifying glass emoji!')

            # counter
            upscaled_message_default = await reaction.message.channel.send("Upscaling image...")
            countdown_message = await reaction.message.channel.send("7")
            for i in range(6, 0, -1):
                await countdown_message.edit(content=str(i))
                await asyncio.sleep(1)

                # delete the countdown message
                if i == 1:
                    await countdown_message.delete()
                    await upscaled_message_default.edit(content="Image will be sent shortly...")

            # calculate the time elapsed
            start_time = time.time()

            # implement upscale functionality here
            # upscale the image
            # check if the message has any attachments
            if reaction.message.attachments:
                image_url = reaction.message.attachments[0].url  # get the URL of the first attachment

                async with aiohttp.ClientSession() as session:
                    # Download the image
                    async with session.get(image_url) as resp:
                        image_bytes = await resp.read()

                    # Get the height of the image
                    image = Image.open(io.BytesIO(image_bytes))
                    height = image.height

                    # Upscale the image
                    data = FormData()
                    data.add_field('image', image_bytes, filename='image.png', content_type='application/octet-stream')
                    data.add_field('height', str(2048)) 

                    async with session.post(
                        "https://api.stability.ai/v1/generation/esrgan-v1-x2plus/image-to-image/upscale",
                        headers={
                            "Accept": "application/json",
                            "Authorization": f"Bearer " + stability_token,
                        },
                        data=data
                    ) as response:
                        if response.status != 200:
                            raise Exception("Non-200 response: " + str(await response.text()))

                        data = await response.json()

            # calculate the time elapsed
            end_time = time.time()
            
            for i, image in enumerate(data["artifacts"]):
                image_bytes = base64.b64decode(image["base64"])
                image_file = io.BytesIO(image_bytes)
                image_file.name = f'upscale_{image["seed"]}.png'
                await reaction.message.channel.send(file=discord.File(image_file))

        # delete the message once the image is upscaled
        await upscaled_message_default.delete()        
        
        # show the time elapsed
        time_elapsed = end_time - start_time
        await reaction.message.channel.send(f"Time elapsed: {time_elapsed:.2f} seconds")

        # check if the reaction is the trash can emoji
        if str(reaction.emoji) == '🗑️':
            await reaction.message.channel.send('You clicked the trash can emoji!')
            # implement delete functionality here
            await reaction.message.delete()
            await reaction.message.channel.send('Message deleted!')

## Set up and log in
url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": "Bearer " + stability_token,
}                    
client = MyClient()

client.run(discord_token)


