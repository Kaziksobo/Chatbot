from transformers import BlenderbotTokenizer, BlenderbotForConditionalGeneration
from csv import writer, reader
from os import path, remove
from time import time
from datetime import datetime
from typing import Union
from nltk.corpus import words
from nltk import word_tokenize
import torch, re, nltk.data, psutil

def log_reader(file_address: str, format: bool=False, len_limit: bool=False) -> list:
    """Reads the contents of the log file into a single list, ignoring the time taken and log time columns.\n
    Also has the option of formatting the chat history, turning each message into a dictionary,
    specifying if the message came from the model or the user"""
    
    # If chat history does not exist, function returns none
    if not path.exists(file_address):
        print('No log file found')
        return None

    # Function continues here if the chat history exists
    print('Log file found')
    with open(file_address, 'r') as log_file:
        csv_reader = reader(log_file)
        chat_history = []
        # Create a list of messages in chat history
        for row in csv_reader:
            # Ignores header row
            if 'User message' in row:
                continue
            # Appends the first two entries in the row to the chat_history list
            chat_history.extend((row[0], row[1]))
    
    # Reverses the list so that the most recent messages are first (new - old)
    chat_history.reverse()
    
    if format:
        chat_history = format_chat_history(chat_history, len_limit)
    
    return chat_history

def format_chat_history(chat_history: list, len_limit: bool) -> list:
    """Formats messages in chat history in form:\n
    {
        'type': 'ai' or 'user',
        'text': message content
    }"""
    
    formatted_chat_history = []
    # If the length of the chat history should be limited, the length will be limitted to 9 messages
    # This will be done by only putting up to the first 9 messages into the new formatted list
    # 9 is chosen as it is the number of available message bubbles on the display
    if len_limit:
        for i in range(min(9, len(chat_history))):
            # Messages with even indexes are AI messages, whilst ones with odd indexes are user messages
            if i % 2 == 0:
                formatted_chat_history.append({'type': 'ai', 'text': chat_history[i]})
            else:
                formatted_chat_history.append({'type': 'user', 'text': chat_history[i]})
    # If the length of the chat history should not be limited, the entire history is formatted
    else:
        for i in range(len(chat_history)):
            if i % 2 == 0:
                formatted_chat_history.append({'type': 'ai', 'text': chat_history[i]})
            else:
                formatted_chat_history.append({'type': 'user', 'text': chat_history[i]})

    return formatted_chat_history

def message_id_generator(chat_history: list) -> list:
    """Adds IDs to each message based on their location in the list\n
    Each message in the chat history should now be in the form:
    {
        'type': 'ai' or 'user',
        'text': message content,
        'id': between 'message-1' and 'message-9'
    }"""
    
    for i in range(len(chat_history)):
        chat_history[i]['id'] = f'message-{i + 1}'
    
    return chat_history



def reply_generator(message: str) -> Union[str, float]:
    # sourcery skip: extract-duplicate-method
    """Uses Blenderbot to generate a reply to the inputted message"""
    
    # The exact time at the start of the message generation process is saved
    start = time()
    name = 'facebook/blenderbot-400M-distill'

    print(f'Input sequence: {message}')

    # Declares tokenizer
    # Checks specified cache directory for tokenizer, if tokenizer not present it will be downloaded
    tokenizer = BlenderbotTokenizer.from_pretrained(name, cache_dir='data/tokenizers')

    print('Tokenizing input')

    # Tokenizes input, adding special tokens and returning PyTorch tensors
    input_ids = tokenizer.encode(
        message,
        add_special_tokens=True,
        is_split_into_words=False,
        return_tensors='pt',
    )

    print(f'Input Ids: {input_ids}')
    
    reply_ids = model_generation(name, input_ids)
    
    # Decodes tokens from model, avoiding special tokens so they do not appear in the input
    reply = tokenizer.decode(reply_ids[0], skip_special_tokens=True)

    print(f'Response: {reply}')
    
    # The exact time at the end of the message generation process is saved
    end = time()
    
    # Returns message, and the time taken is calculated by subtracting the exact time at the start from the time at the end
    return format_message(reply), round((end - start), 2)

def model_generation(name: str, input_ids: torch.Tensor) -> torch.Tensor:
    """Uses BlenderBot to generate a response sequence to the inputted tokens, with beam search for text generation"""
    
    # Declares model
    model = BlenderbotForConditionalGeneration.from_pretrained(name, cache_dir='data/models')
    
    num_beams = beams_calc()
    
    print('Generating reply ids')
    # Generates Reply ids using beam search to generate text
    result = model.generate(
        input_ids, 
        num_beams=num_beams, 
        max_length=60
    )
    print(f'num_beams used: {num_beams}')
    print(f'Reply Ids: {result}')
    
    return result

def beams_calc() -> int:
    """Calculate num_beams to use in model generation based on CPU frequency.
    Currently flips between 35 beams in above 3.4GHz, otherwise uses 1 beam"""
    
    cpu_freq = psutil.cpu_freq()
    cpu_freq = cpu_freq.max

    return 35 if cpu_freq > 3400 else 1

def format_message(message: str) -> str:
    """Formats message to capitalise and remove whitespace and fix some grammar errors"""
    
    # Fixes formatting of full stops, with no space before and one space after
    message = re.sub(r'\s(?=[\.,:;])', "", message)
    # Removes any whitespace from the start and end of the message
    message = message.strip()
    # Capitalises any bare Is
    message = message.replace(' i ', ' I ')
    # Uses NLTK to split the message into a list of sentences
    sent_tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
    sentences = sent_tokenizer.tokenize(message)
    # Capitalises each sentence and joins it back together into one string
    sentences = [sent.capitalize() for sent in sentences]
    message = ' '.join(sentences)
    
    return message

def english_check(message: str) -> bool:
    """Checks if the message is understandable english by tokenizing it into words, and checking if at least one of them is in the dictionary"""
    
    # Used NLTK word tokenizer to split the message into a list of words
    words_list = word_tokenize(message)
    return any(word.lower() in words.words() for word in words_list)


def log(user_message: str, bot_response: str, time_taken: float) -> None:
    # sourcery skip: extract-method
    """Logs the user's message, the bot response and the computation time to a CSV file"""
    
    # Checks if both of the log files exists, creating them if they don't
    file_address = 'log.csv'
    extended_file_address = 'ext_log.csv'
    for file in [file_address, extended_file_address]:
        if not path.exists(file):
            create_log_file(file)

    # Checking if the main log file is full
    with open(file_address, 'r', encoding='utf-8', newline='') as file_object:
        # As the limit is 10 message-response pairs, this checks if the file is more than 11 rows long (10 pairs and the header row)
        limit_reached = sum(1 for _ in file_object) == 11
    if limit_reached:
        print('Log file limit reached')

        # Reading in all rows from original file
        rows = []
        with open(file_address, 'r', encoding='utf-8', newline='') as log_file:
            csv_reader = reader(log_file)
            rows.extend(iter(csv_reader))
            
        # Removing oldest message row and header row (the first two rows read into the list)
        rows.pop(0)
        rows.pop(0)
        # OS.remove is used to delete the file
        remove(file_address)
        create_log_file(file_address)

        # Writing older rows to new log file
        with open(file_address, 'a', encoding='utf-8', newline='') as file_object:
            csv_writer = writer(file_object)
            for row in rows:
                csv_writer.writerow(row)

    # Logging new data to both log files
    print('Logging data')
    # Storing the exact time the data is being logged
    log_time = str(datetime.now())
    # Logging the data into both log files
    log_file_writer(user_message, bot_response, time_taken, file_address, log_time)
    log_file_writer(user_message, bot_response, time_taken, extended_file_address, log_time)
        
def log_file_writer(user_message: str, bot_response: str, time_taken: str, file_address: str, log_time:str) -> None:
    """Logs data to any log file"""
    
    # Writes a row of data into the specified file
    with open(file_address, 'a', encoding='utf-8', newline='') as file_object:
        csv_writer = writer(file_object)
        csv_writer.writerow([user_message, bot_response, time_taken, log_time])

def create_log_file(file_address: str) -> None:
    """Creates the log file, adding in the header row"""
    
    # Attempts to open the file in write mode which will create the file if it cannot be found
    print('Creating new log file')
    with open(file_address, 'w', encoding='utf-8', newline='') as file_object:
        csv_writer = writer(file_object)
        # Write the header row to the newly created, empty file
        csv_writer.writerow(['User message', 'Bot response', 'Time taken', 'Log time'])

def log_report(user_message: str, bot_response: str, report_reason: str):
    """Saves reported response, user's message and report reason to a CSV file"""
    
    # If the file does not exist, it is created
    if not path.exists('report.csv'):
        create_report_file()
    
    # Writes a row of data to the report CSV file
    with open('report.csv', 'a', encoding='utf-8', newline='') as file_object:
        csv_writer = writer(file_object)
        csv_writer.writerow([user_message, bot_response, report_reason])

def create_report_file() -> None:
    """Creates report file, adding in the header row"""
    
    # Attempts to open the file in write mode which will create the file if it cannot be found
    print('Creating report file')
    with open('report.csv', 'w', encoding='utf-8', newline='') as file_object:
        csv_writer = writer(file_object)
        # Write the header row to the newly created, empty file
        csv_writer.writerow(['User message', 'Bot response', 'Report reason'])



def message_selector(length: int, location: int) -> int:
    """selects the messages to be displayed when a message is searched for, 
    based off the length of the chat history\n
    Up to 9 messages should be displayed, with the number before and after the query varying 
    depending on the position of the query message in the list and the length of the list.\n
    This function is necessary to ensure that the algorithm never wraps round 
    and starts displaying messages from other parts of the list"""
    
    messages_before = 0
    messages_after = 0
    # Calculates the number of messages available in the list on either side of the query
    messages_after_query = length - (location + 1)
    messages_before_query = length - (messages_after_query + 1)
    # If there is at least 4 messages available on either side of the query, than 4 messages will be displayed from either side of the query
    if messages_after_query > 3 and messages_before_query > 3:
        messages_after = 4
        messages_before = 4
    # If there are less than 4 messages available after the query, than all messages available to be displayed after the query will be,
    # and an appropriate number of messages will be displayed before to ensure that there are 9 messages shown in total
    elif messages_after_query < 4 and messages_before_query > 3:
        messages_after = messages_after_query
        messages_before = 8 - messages_after
    # If there are less than 4 messages available before the query, than all messages available to be displayed before the query will be,
    # and an appropriate number of messages will be displayed after to ensure that there are 9 messages shown in total
    elif messages_after_query > 3 and messages_before_query < 4:
        messages_before = messages_before_query
        messages_after = 8 - messages_before
    
    return messages_before, messages_after

def get_messages_list() -> list:
    """Returns a list of the text content of all the messages, in a list with each element containing a message"""
    
    history = log_reader('ext_log.csv', format=True)
    history.reverse()

    return [message['text'] for message in history]
