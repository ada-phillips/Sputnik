import abc

class Action(abc.ABC):

    @property
    @abc.abstractmethod
    def editable(self):
        return False

    @property
    @abc.abstractmethod
    def undoable(self):
        return False

    @abc.abstractmethod
    async def execute(self):
        pass

    @abc.abstractmethod
    async def undo(self):
        pass
    
    @abc.abstractmethod
    async def replace(self, new_outcome):
        pass

class SentMessage(Action):
    def __init__(self, replies, channel):
        self.message = None
        self.channel = channel
        self.reply = reply
    
    async def execute(self):
        self.message = await channel.send(content=reply.content, files=reply.files, embed=reply.embed)
    
    async def undo(self):
        await message.delete()
    
    async def replace(self, new_reply):
        await message.edit(content=new_reply.content, embed=new_reply.embed)

class sendMessage(Action):
    send the message, and return SentMessage