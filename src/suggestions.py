import trello
import logging

log = logging.getLogger(__name__)

class SuggestionList():
    def __init__(self, api_key, api_secret, oauth_token, oauth_secret, new_card_list):
        self.client = trello.TrelloClient(api_key, api_secret=api_secret, token=None, token_secret=None)
        self.board = self.client.list_boards()[0]
        self.new_card_list = self.board.get_list(new_card_list)

    def get_suggestions(self):
        out = []
        for column in self.board.list_lists():
            for card in column.list_cards():
                out.append(card)
        return out
    
    def get_suggestion_categories(self):
        out = {}
        for column in self.board.list_lists():
            col_out=[]
            for card in column.list_cards():
                col_out.append(card)
            out[column.name]=col_out
        return out

    def add_suggestion(self, title, description, author):
        card = self.new_card_list.add_card(title, desc=description)
        for field in self.board.get_custom_field_definitions():
            if field.name=="Suggested By":
                card.set_custom_field(author, field)
            elif field.name=="Suggested On":
                card.set_custom_field(card.created_date.isoformat(), field)





