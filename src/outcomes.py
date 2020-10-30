import abc

log = logging.getLogger(__name__)

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

class SentMessages(Action):
    def __init__(self, replies, channel):
        self.messages = []
        self.channel = channel
        self.replies = replies
    
    async def execute(self):
        for reply in replies:
            self.messages.append(await channel.send(content=reply.content, files=reply.files, embed=reply.embed))
    
    async def undo(self):
        for message in messages:
            await message.delete()
    
    async def replace(self, new_replies):
        if (messages.length<new_replies.length):

        for message in messages:
            await message.edit(content=new_reply.content, embed=new_reply.embed)

class sendMessage(Action):
    send the message, and return SentMessage