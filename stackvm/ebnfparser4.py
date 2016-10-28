# -*- coding: utf-8 -*-
"""
Created on Mon Oct 17 21:00:40 2016

@author: Josh
"""
from string import ascii_lowercase, ascii_uppercase, whitespace
from itertools import groupby, islice, cycle
import logging
from collections import Counter

logging.basicConfig(level=logging.INFO,
                    format="%(funcName)s:%(levelname)s:%(message)s")

from tokenizer import Symbol, BaseLexer, Token

class TerminalSymbol(Symbol):
    _next_id = 1
    is_terminal = True


class NonTerminalSymbol(Symbol):
    _next_id = 1000
    is_terminal = False


# Tokens for the EBNF Tokenizer and Parser
STARTREPEAT = TerminalSymbol('STARTREPEAT')
ENDREPEAT = TerminalSymbol('ENDREPEAT')
STARTGROUP = TerminalSymbol('STARTGROUP')
ENDGROUP = TerminalSymbol('ENDGROUP')
STARTOPTION = TerminalSymbol('STARTOPTION')
ENDOPTION = TerminalSymbol('ENDOPTION')
OR = TerminalSymbol('OR')
REP = TerminalSymbol('*')
OPT = TerminalSymbol('?')
ATL = TerminalSymbol('+')
SYMBOL = TerminalSymbol('SYMBOL')
LITERAL = TerminalSymbol('LITERAL')
RULE = TerminalSymbol('RULE')
SEQUENCE = NonTerminalSymbol('SEQUENCE') # token lexeme is name of rule
ALTERNATING = NonTerminalSymbol('ALTERNATING')
REPEATING = NonTerminalSymbol('REPEATING')
OPTIONAL = NonTerminalSymbol('OPTIONAL')
ATLEASTONCE = NonTerminalSymbol('ATLEASTONCE')

class EBNFToken(Token):

    def __str__(self):
        return "<{} '{}'>".format(self.symbol.name, self.lexeme)

    def __repr__(self):
        return "<EBNFToken {} {}>".format(self.symbol.name, self.lexeme)

    @property
    def is_terminal(self):
        return self.symbol.is_terminal

    @Token.symbol.setter
    def symbol(self, newsymbol):
        if not isinstance(newsymbol, Symbol):
            raise ValueError("cannot update EBNFToken symbol to non Symbol")
        self._symbol = newsymbol


class EBNFTokenizer(BaseLexer):

    def __init__(self, *args, **kwargs):
        BaseLexer.__init__(self, *args, **kwargs)
        self.tokenclass = EBNFToken

#    def _emit(self, symbol,):
#        super()._emit(symbol)

    def _lex_start(self):
        assert self._start == self._pos

        peek = self._peek

        if peek is None:
            return self._lex_eof

        elif peek in whitespace:
            return self.skip_whitespace()

        elif peek == '"':
            return self.get_quoted_string()

        elif peek in '{}':
            self._skip()
            self._emit(STARTREPEAT if peek=='{' else ENDREPEAT)
            return self._lex_start

        elif peek in '()':
            self._skip()
            self._emit(STARTGROUP if peek=='(' else ENDGROUP)
            return self._lex_start

        elif peek in '[]':
            self._skip()
            self._emit(STARTOPTION if peek=='[' else ENDOPTION)
            return self._lex_start

        elif peek == '|':
            self._accept_run('|')
            self._emit(OR)
            return self._lex_start

        elif peek == '*':
            self._accept_run('*')
            self._emit(REP)
            return self._lex_start

        elif peek == '?':
            self._accept_run('?')
            self._emit(OPT)
            return self._lex_start

        elif peek == '+':
            self._accept_run('+')
            self._emit(ATL)
            return self._lex_start

        elif peek in ascii_lowercase:
            return self.get_rule()

        elif peek in ascii_uppercase:
            return self.get_symbol()

    def get_symbol(self):
        self._accept_run(ascii_uppercase)
        self._emit(SYMBOL)
        return self._lex_start

    def get_rule(self):
        self._accept_run(ascii_lowercase)
        self._emit(RULE)
        return self._lex_start


    def skip_whitespace(self):
        self._accept_run(whitespace)
        self._ignore()
        return self._lex_start

    def get_quoted_string(self):
        self._skip() # over opening quote
        self._accept_until('"')
        self._emit(LITERAL)

        # raise unterminated if next character not closing quote
        if self._peek != '"':
            raise SyntaxError("unterminated quote")
        self._skip()

        return self._lex_start

    def _lex_eof(self):
        assert self._start == self._pos == self._len
        return None

class ParserNode(object):
    def __init__(self, token):
        self.token = token
        self.children = []
        self.alternate = False
        self.optional = False
        self.repeating = False
        self.oneormore = False

    def add(self, thing):
        assert isinstance(thing, ParserNode)
        self.children.append(thing)

    def __str__(self):
        if len(self.children) > 1:
            flags = ["alternate" if self.alternate else "",
                     "optional" if self.optional else "",
                     "repeating" if self.repeating else ""]
            if any(flags):
                flagstr = ", ".join(f for f in flags if f)
            else:
                flagstr = "sequence"
        else:
            flagstr = ""
        return "<ParserNode {} {}>".format(self.token, flagstr)

    __repr__ = __str__

def split_by_or(iterable):
    return [list(g) for k,g in groupby(iterable, lambda x:x.token.symbol == OR) if not k]

groupcount = Counter()
helper = {STARTGROUP: SEQUENCE, STARTREPEAT: REPEATING, STARTOPTION: OPTIONAL}
suffix = {REP: REPEATING, OPT: OPTIONAL, ATL: ATLEASTONCE}

groupings = {STARTGROUP: ENDGROUP, STARTREPEAT: ENDREPEAT, STARTOPTION: ENDOPTION}

def make_parser_node(name, tokens, endtoken = None):
    global groupcount
    if not tokens:
        return None, []
    logging.debug("make_parser_node for '%s' with %d tokens", name, len(tokens))
    this = ParserNode(EBNFToken(SEQUENCE, name))
    logging.debug("this is %d", id(this))

    while tokens:
        first = tokens[0]

        if first.symbol in [STARTGROUP, STARTREPEAT, STARTOPTION]:
            logging.debug("found %s in %d", first.symbol.name, id(this))
            key = name.split('-')[0]
            groupcount[key] += 1
            child, tokens = make_parser_node("%s-%d" % (key, groupcount[key]),
                                             tokens[1:],
                                             groupings[first.symbol])
            if child:
                child.token.symbol = helper[first.symbol]
                this.add(child)

        elif first.symbol in [ENDGROUP, ENDREPEAT, ENDOPTION]:
            logging.debug("Found %s with %d tokens left in %d", first.symbol.name, len(tokens), id(this))
            if endtoken != first.symbol:
                raise SyntaxError("Expected %s to close group, got %s" % (endtoken.name, first.symbol.name))
            used_brackets = False
            if first.symbol == ENDREPEAT:
                #this.children[-1].repeating = True
                #this.name = EBNFToken(REPEATING, name)
                used_brackets = True
            elif first.symbol == ENDOPTION:
                #this.children[-1].optional = True
                used_brackets = True

            if len(tokens) > 1:
                # todo: move this check to the tokenizer where it belongs
                if used_brackets and tokens[1].symbol in [REP, OPT, ATL]:
                    logging.error("Illegal mix of brackets and suffixes in %s", name)
                    raise SyntaxError("Illegal mix of {} and ()*  in %s" % name)
                if tokens[1].symbol in [REP, OPT, ATL]:
                    #new_name = this.token.lexeme + str(groupcount)
                    this.token.symbol = suffix[tokens[1].symbol]
                    logging.debug("Changed %d to symbol %s", id(this), this.token.symbol)
                    tokens.pop(0)

            return this, tokens[1:]

        elif first.symbol == OR:
            logging.debug("Found or in %d with symbol %s", id(this), this.token.symbol)
            this.alternate = True
            this.token.symbol = ALTERNATING
            logging.debug("Changed %d to symbol %s", id(this), this.token.symbol)
            this.add(ParserNode(first))
            tokens.pop(0)

        else:
            this.add(ParserNode(first))
            tokens.pop(0)

    logging.debug("Returning %d with %d tokens", id(this), len(tokens))
    return this, tokens


class ParseTreeNode(object):
    """This node represents the parsed code
    """
    def __init__(self, token):
        self.token = token
        self.children = []

    def __str__(self):
        return "<ParseTreeNode:{} {} >".format(self.token.symbol.name, self.token.lexeme)

def print_parsetree(ast, ind=0):
    print("{0}< {1} >".format(indent(ind), ast.token.lexeme))
    for child in ast.children:
        print_parsetree(child, ind+2)

def lexemes(tokens):
    return '"{}"'.format(" ".join(t.lexeme for t in tokens))

def token_lexemes(tokens):
    return '"{}"'.format(" ".join(t.token.lexeme for t in tokens))

_indent = " :   "
def indent(x):
    return ''.join(islice(cycle(_indent), x))

class EBNFParser(object):
    """
    Class to read EBNF text and return a dictionary of rules
    plus a dictionary of (name, Symbol) pairs
    """

    def __init__(self, text):
        self.symbol_table = {}
        self.report = []
        self.start_rule = None
        self.collapse_tree = True
        logging.debug("EBNFParser.__init__() start")
        lines = [line for line in text.split(';') if line.strip()]
        data = [line.partition(":=") for line in lines]
        self.rules = {}
        for key, junk, val in data:
            if self.start_rule is None:
                self.start_rule = key.strip()
            parser_node, remaining = make_parser_node(key.strip(), list(EBNFTokenizer(val)))
            if remaining:
                logging.exception("rule %s did not process correctly", key)
                raise SyntaxError("rule %s did not process correctly" % key)
            self.rules[key.strip()] = parser_node
        logging.debug("EBNFParser.__init__() end")

        self._rule_count = 0
        self._calls = Counter()

    def print_report(self):
        width1 = max(len(a) for a,b,c in self.report)
        width2 = max(len(b) for a,b,c in self.report)
        width3 = max(len(c) for a,b,c in self.report)
        print('-'*(width1+width2+width3+4))
        for a,b,c in self.report:
            print("{0:<{3}}  {1:<{4}}  {2:>{5}}".format(a, b, c, width1, width2, width3))

    def parse(self, tokens):
        """Parse tokens into an ParseTreeNode tree"""
        if not self._start_rule:
            raise ValueError("no start rule established")
        self.match_rule(self._start_rule, tokens)

    def match_rule(self, rule, tokens, i = 0):
        """Given a rule name and a list of tokens, return an
        ParseTreeNode and remaining tokens
        """
        parser_node = self.rules.get(rule)
        #print(indent(i), "trying rule", parser_node.token.lexeme, token_lexemes(parser_node.children), lexemes(tokens))
        self.report.append((rule, token_lexemes(parser_node.children), lexemes(tokens)))
        self._rule_count += 1
        #self._calls['match_rule'] += 1
        if self._rule_count > 100:
            raise ValueError("trying too many times")

        if parser_node is None:
            logging.exception("No rule for %s", rule)
            raise SyntaxError("No rule for {}".format(rule))

        logging.debug("matching rule %s for %d tokens with %s", rule, len(tokens), parser_node)

        if not isinstance(parser_node.token, EBNFToken):
            raise ValueError("parser node missing required EBNFToken")


        node, tokens = self.match(parser_node, tokens, i)
        if i == 0 and tokens:
            raise ValueError("not all input consumed")
        return node, tokens

    def match(self, parser_node, tokens, i):
        #print(indent(i),"match %s against %s with %d remaining" % (parser_node.token.lexeme, tokens[0].lexeme, len(tokens)))
        if parser_node.token.is_terminal:
            res, tokens = self.match_terminal(parser_node, tokens, i)
        else:
            res, tokens = self.match_nonterminal(parser_node, tokens, i)
        #print(indent(i), "match returning (%s, %s)" % (res, lexemes(tokens)))
        return res, tokens

    def match_terminal(self, parser_node, tokens, i):
        #self._calls['match_terminal'] += 1
        #self._calls[parser_node.token.symbol.name] += 1

        logging.debug("matching terminal with %s for %d tokens", parser_node, len(tokens))
        if not tokens:
            return None, tokens

        node = ParseTreeNode(parser_node.token.lexeme)

        if parser_node.token.symbol == RULE:
            child, tokens = self.match_rule(parser_node.token.lexeme, tokens, i+1)
            if child is not None:
                # collapse_tree shortens long descendencies with only one child at the end
                if self.collapse_tree and len(child.children) == 1:
                    node.children.append(child.children[0])
                else:
                    node.children.append(child)
            #else:
                #return None, tokens
                #raise SyntaxError("did not match rule %s" % parser_node.token.lexeme)
        elif parser_node.token.symbol == LITERAL:

            if parser_node.token.lexeme == tokens[0].lexeme:
                logging.debug("matching literal .. matched")
                #print(indent(i), "ate literal", tokens[0].lexeme)
                node.children.append(ParseTreeNode(tokens[0]))
                return node, tokens[1:]

            else:
                logging.debug("matching literal .. nope")
                return None, tokens
        elif parser_node.token.lexeme == tokens[0].symbol.name:
            logging.debug("matching symbol %s", parser_node.token.lexeme)
            #print(indent(i), "ate terminal", tokens[0].lexeme)
            node.children.append(ParseTreeNode(tokens[0]))
            return node, tokens[1:]
        else:
            logging.debug("did not match terminal %s", parser_node)
            return None, tokens
        return node, tokens

    def match_nonterminal(self, parser_node, tokens, i):
        #self._calls[parser_node.token.symbol.name] += 1
        # print(indent(i),"match_nonterminal '%s' with %d children against %d tokens" % (parser_node.token.lexeme, len(parser_node.children), len(tokens)))
        node = ParseTreeNode(parser_node.token)
        if not tokens:
            return None, tokens

        child = None

        if parser_node.alternate:
            child, tokens = self.match_alternate(parser_node, tokens, i+1)

        elif parser_node.token.symbol == REPEATING:
            logging.debug("Handle repeating elements (0 or more)")
            #print(indent(i),"Matching Repeating Element", parser_node.token.lexeme)
            child, tokens = self.match_repeating(parser_node, tokens, i+1)

        elif parser_node.token.symbol == SEQUENCE: # match a sequence
            #print(indent(i),"Matching sequence:", token_lexemes(parser_node.children))
            found, tokens = self.match_sequence(parser_node.token.lexeme, parser_node.children, tokens, i+1)
            #print(indent(i), "matched sequence, extending with", found)
            node.children.extend(found)

#        elif parser_node.token.symbol == RULE:
#            child, tokens = self.match_rule(parser_node.token.lexeme, tokens, i+1)

        else:
            raise SyntaxError("ran out of options in match_nonterminal")

        if child is not None:
            #print(indent(i), "matched nonterminal, extending with", token_lexemes(child.children))
            node.children.extend(child.children)

        if node.children:
            return node, tokens
        else:
            return None, tokens



    def match_repeating(self, parser_node, tokens, i):
        #self._calls['match_repeating'] += 1
        token = parser_node.token
        expected = parser_node.children
        node = ParseTreeNode(token)
        logging.debug("match repeating")
        keep_trying = True
        while keep_trying:
            #print(indent(i),"match repeating for", token, expected, tokens)
            addends, tokens = self.match_sequence(token.lexeme, expected, tokens, i+1)
            #print(indent(i),"from match_sequence:", addends, tokens)
            if addends:
                node.children.extend(addends)
                #print_parsetree(node, i)

            else:
                keep_trying = False
                logging.debug("returning node with %d children", len(node.children))

        if node.children:
            return node, tokens
        else:
            return None, tokens

    def match_alternate(self, parser_node,  tokens, i):
        """rulename is the name. Alternates is a list of lists. Tokens a list of tokens"""
        #self._calls['match_alternate'] += 1
        logging.debug("match_alternate for %s", parser_node)
        if not tokens:
            return None, tokens

        alternates = split_by_or(parser_node.children)

        node = ParseTreeNode(parser_node.token)

        for alternate in alternates:
            preview = tokens[0] if tokens else "No tokens"
            logging.debug("trying alternate: %s against %s", ["%s|%s" % (e.token.symbol.name, e.token.lexeme) for e in alternate], preview)
            #print(indent(i),"trying alternate", token_lexemes(alternate))
            found, tokens = self.match_sequence(parser_node.token.lexeme, alternate, tokens, i+1)
            if found:
                logging.debug("..got it!")
                #print(indent(i), "matched alternate", token_lexemes(alternate))
                node.children.extend(found)
                #print_parsetree(node, i+1)
                return node, tokens
            else:
                #print(indent(i), "did not match alternate", token_lexemes(alternate))
                logging.debug("..nope")
        #print(indent(i),"all alternates failed")
        return None, tokens
        #logging.exception("match_alternate failed in %s", rulename)
        #raise SyntaxError("match_alternate failed in %s" % rulename)

    def match_sequence(self, name, originals, tokens, i):
        """returns a list of ParseTreeNodes and a list of remaining tokens"""
        #self._calls['match_sequence'] += 1
        expected = list(originals) # should create a copy

        found = []
        original_tokens = list(tokens)
        found_one_thing = False
        while expected:
            this = expected[0]
            if not tokens:
                #print(indent(i),"sequence '%s' out of tokens, bailing" % name)
                return found, tokens
            #print(indent(i), "expecting in '%s': '%s', got '%s'" % (name, this.token.lexeme, tokens[0].lexeme), end='')
            #print(" (%d expected items)" % (len(expected)+1)) # add one because we popped the value from expected
            if tokens:
                logging.debug("expecting: %s got %s", this, tokens[0])
            else:
                logging.debug("expecing: %s with no tokens", this)
            node, tokens = self.match(this, tokens, i+1)
            if node is not None:
                #print(indent(i), "found", token_lexemes(node.children))
                found.extend(node.children)
                found_one_thing = True
            else:
                #print(indent(i), "sequence failed on", this.token.lexeme)
                return  found, tokens
            expected.pop(0)
            #print(indent(i), 'end of sequence loop, expecting: %s against %s' % (token_lexemes(expected), lexemes(tokens)), originals)

        #print(indent(i),"Out of expectations. Node has", len(found), "child%s" % ("" if len(found)==1 else "ren"))
        return found, tokens

def print_node(node, ind=0):
    print(indent(ind), str(node))
    for child in node.children:
        print_node(child, ind+2)


def test(text):
    groupcount['test'] = 0
    node, detritus = make_parser_node('test', list(EBNFTokenizer(text)))
    print_node(node)
    print(detritus)

def test_repeat():
    p = EBNFParser("""as := "a" {("b" | "c")};""")
    print_node(p.rules['as'])
    logging.root.setLevel(logging.INFO)
    a = Token(LITERAL, "a")
    b = Token(LITERAL, "b")
    c = Token(LITERAL, "c")
    node, detritus = p.match_rule('as', [a, c, b, c])
    print_parsetree(node)
    print(detritus)

if __name__ == '__main__':
    text = """expr := term {("+" | "-") term};
            term := factor {("*" | "/") factor};
            factor := NUMBER | "(" expr ")";
            """
    text2 = """expr := (term ("+" | "-") term | term);
            term := (factor ("*" | "/") factor | factor);
            factor := NUMBER | "(" expr ")";
            """
    logging.root.setLevel(logging.INFO)
    p = EBNFParser(text)

    #print_node(p.rules['expr'])
    #print_node(p.rules['term'])
    #print_node(p.rules['factor'])

    # test language - simple math
    NUMBER = TerminalSymbol("NUMBER")
    OP = TerminalSymbol("OP")
    PARENS = TerminalSymbol("PARENS")
    expr = NonTerminalSymbol('expr')
    term = NonTerminalSymbol("term")
    factor = NonTerminalSymbol("factor")

    from string import digits

    ops = "+-/*"
    parens = "()"

    class MathLexer(BaseLexer):
        def _lex_start(self):
            assert self._start == self._pos

            peek = self._peek

            if peek is None:
                assert self._start == self._pos == self._len
                return None

            elif peek in whitespace:
                self._accept_run(whitespace)
                self._ignore()
                return self._lex_start

            elif peek in digits:
                self._accept_run(digits)
                self._emit(NUMBER)
                return self._lex_start

            elif peek in ops:
                self._accept_run(ops)
                self._emit(OP)
                return self._lex_start

            elif peek in parens:
                self._accept_run(parens)
                self._emit(PARENS)
                return self._lex_start


#    test = list(MathLexer("3"))
#    logging.root.setLevel(logging.INFO)
#    print("testing:", test)
#    node, detritus = p.match_rule('factor', test)
#    print_parsetree(node)
#    print(detritus)

    logging.root.setLevel(logging.INFO)
    parenstest = list(MathLexer("2*(7+3)"))
    print("testing:", parenstest)
    p.collapse_tree = False
    node, detritus = p.match_rule('expr', parenstest)
    _indent = " "
    print_parsetree(node)
    print(detritus)

#    math_test = list(MathLexer("3 + 2"))
#    print("testing:", math_test)
#    logging.root.setLevel(logging.DEBUG)
#    node, detritus = p.match_rule('expr', math_test)
#    print_parsetree(node)
#    print(detritus)



