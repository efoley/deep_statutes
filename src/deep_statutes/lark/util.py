from lark import Lark, Tree, UnexpectedInput


END_ACTION = '$END'

def find_matches(text: str, start: str,lark: Lark) -> tuple[list[Tree], list[int]]:
    """
    Returns:
        - a list of parse trees that match the input text
        - a list of the ending positions of each parse tree in the input text
    """
    matched_parse_trees = []
    token_end_pos = []
    if not lark.options.parser == 'lalr':
        raise ValueError("Only lalr parser is supported")
    
    pi = lark.parse_interactive(text, start=start)
    lex_stream = pi.lexer_thread.lex(pi.parser_state)
    last_token_end_pos = 0
    while True:
        # check if we are in the valid end state for a rule
        choices = pi.choices()
        if END_ACTION in choices:
            #valid_parses.append(choices[END_ACTION])
            # we feed the parser EOF to trick it into giving us back the parse tree for
            # this range of the input text
            r = pi.copy().feed_eof()
            matched_parse_trees.append(r)
            token_end_pos.append(last_token_end_pos)
        try:
            token = next(lex_stream)
            last_token_end_pos = token.end_pos
        except StopIteration:
            break
        except UnexpectedInput as e:
            break
        pi.feed_token(token)

    return matched_parse_trees, token_end_pos