import flask
from flask import Flask, render_template, request
from os import remove, path
from app_functions import (
    reply_generator, 
    log, log_reader, 
    message_id_generator, 
    format_message, 
    message_selector, 
    create_log_file, 
    log_report, 
    get_messages_list,
    english_check
)

current_theme = 'light'
current_page = 'index.html'
stylesheet = 'static/light-styles.css'
chat_history = []
messages_to_display = []
query_message = ''
reported_message = ''

app = Flask(__name__)

@app.route('/')
def main() -> flask.Response:
    """Displays the home page 'index.html' and clears temp logs"""
    
    global stylesheet, current_page
    
    # Deletes and recreates main log file
    if path.exists('log.csv'):
        remove('log.csv')
    create_log_file('log.csv')
    if not path.exists('ext_log.csv'):
        create_log_file('ext_log.csv')
    
    # Render home page with appropriate stylesheet and datalist
    current_page = 'index.html'
    return render_template('index.html', stylesheet=stylesheet, messages_list=get_messages_list())

@app.route('/home', methods=['GET', 'POST'])
def home() -> flask.Response:
    """
    Displayes the home page 'index.html' and clears temp logs \n
    This is the same as the main() function, however is used for when the home button is pressed
    """
    
    global stylesheet, current_page
    
    # Deletes and recreates main log file
    remove('log.csv')
    create_log_file('log.csv')
    
    # Render home page with appropriate stylesheet and datalist
    current_page = 'index.html'
    return render_template('index.html', stylesheet=stylesheet, messages_list=get_messages_list())

@app.route('/message', methods=['GET', 'POST'])
def message() -> flask.Response:
    """Requests the user's message, processes it and renders the messages page with the user's message and AI's reply"""
    
    global stylesheet, current_page, chat_history
    
    # Requesting the data entered into the input form (the search bar) by the user
    user_message = request.form['message-input']
    user_message = format_message(user_message)
    
    if english_check(user_message):
        reply, time = reply_generator(user_message)
    else:
        reply = 'That makes no sense'
        time = 0
    
    log(
        user_message=user_message,
        bot_response=reply,
        time_taken=time
    )

    # Reading in chat history from log file
    chat_history = log_reader('log.csv', format=True, len_limit=True)
    
    # Generating Ids for chat messages to order them with CSS ids
    chat_history = message_id_generator(chat_history)

    # Render message page with chat history, appropriate stylesheet and datalist
    current_page = 'message.html'
    return render_template('message.html', stylesheet=stylesheet, messages=chat_history, messages_list=get_messages_list())

@app.route('/theme', methods=['GET', 'POST'])
def theme_switcher() -> flask.Response:
    """Switches the theme of the web app"""
    
    global current_page, current_theme, stylesheet, chat_history, query_message, reported_message
    
    # Switch stylesheet and theme
    if current_theme == 'light':
        current_theme = 'dark'
        stylesheet = 'static/dark-styles.css'
    else:
        current_theme = 'light'
        stylesheet = 'static/light-styles.css'
    
    # Render current page with corrected stylesheet
    if current_page == 'message.html': 
        return render_template(current_page, stylesheet=stylesheet, messages=chat_history, messages_list=get_messages_list())
    elif current_page == 'search_result.html':
        return render_template(current_page, stylesheet=stylesheet, messages=messages_to_display, messages_list=get_messages_list())
    elif current_page == 'search_error.html':
        return render_template(current_page, stylesheet=stylesheet, message=query_message, messages_list=get_messages_list())
    elif current_page == 'report.html':
        return render_template(current_page, stylesheet=stylesheet, message=reported_message, messages_list=get_messages_list())
    else:
        return render_template(current_page, stylesheet=stylesheet, messages_list=get_messages_list())

@app.route('/search', methods=['GET', 'POST'])
def search() -> flask.Response:
    """Renders searched message plus number of surrounding messages"""
    
    global messages_to_display, current_page, stylesheet, query_message
    
    # Use text input to get query message
    query_message = request.form['search-bar']
    
    print(f'Search query - {query_message}')

    # Get full chat history and reverse
    history = log_reader('ext_log.csv', format=True)
    history.reverse()
    
    # Find location of query message in message history
    location = False
    for message_info in history:
        if message_info['text'] == query_message:
            print(f'Found message - {message_info}')
            location = history.index(message_info)
    
    # If the message could not be found in the history, an error page is rendered, which references the query message
    if not location:
        current_page = 'search_error.html'
        return render_template(current_page, stylesheet=stylesheet, message=query_message, messages_list=get_messages_list())
    
    # Selects the number of messages to show before and after the query message
    messages_before, messages_after = message_selector(len(history), location)
    
    # Uses messages_before and messages_after to create a list of messages to show to the user
    # selects messages from the history with indexes between (location + messages_before) and (location - messages_after + 1)
    messages_to_display = [history[i] for i in range((location + (messages_after)), (location - (messages_before + 1)), -1)]
    
    # Generating Ids for chat messages to order them with CSS ids
    messages_to_display = message_id_generator(messages_to_display)
    
    # Labels the query message to allow it to have different CSS
    for message in messages_to_display:
        if message['text'] == query_message:
            message['class'] = 'query-message-box'
        else:
            message['class'] = False
    
    # Render search results page with the list of searched messages to show, appropriate stylesheet and datalist
    current_page = 'search_result.html'
    return render_template(current_page, stylesheet=stylesheet, messages=messages_to_display, messages_list=get_messages_list())

@app.route('/back', methods=['GET', 'POST'])
def back() -> flask.Response:
    """Renders the message page when back button on search results/search error/report page clicked"""
    
    global chat_history, current_page, stylesheet
    
    # Render message page with chat history, appropriate stylesheet and datalist
    current_page = 'message.html'
    return render_template(current_page, stylesheet=stylesheet, messages=chat_history, messages_list=get_messages_list())

@app.route('/report', methods=['GET', 'POST'])
def report() -> flask.Response:
    """Logs the report and renders report page"""
    
    global stylesheet, chat_history, current_page, reported_message
    
    # Finds the name of the form used to report the message
    # The name of the form contains the id of the message
    reported_message = list(request.form.to_dict().keys())[0]
    # Get the report reason from form
    report_reason = request.form[reported_message]
    # Get message id from report form name
    report_message = reported_message.replace('report-', '')
    
    # Finds the message with the matching message id as to the one from the report form name
    for message in chat_history:
        if message['id'] == report_message:
            location = chat_history.index(message)
            bot_response = message['text']
    reported_message = bot_response
    # Finds the message before the reported message
    user_message = chat_history[location - 1]['text']
    
    log_report(user_message, bot_response, report_reason)
    
    # Render report page with reported message, appropriate stylesheet and datalist
    current_page = 'report.html'
    return render_template(current_page, stylesheet=stylesheet, message=bot_response, messages_list=get_messages_list())

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')