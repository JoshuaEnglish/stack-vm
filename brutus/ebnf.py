# -*- coding: utf-8 -*-
"""
ebnf.py

Parses DSL text into Concrete Syntax Tree Nodes via REBNF rules.

"""

import logging
from collections import OrderedDict, Counter
from itertools import groupby

from .tokenizer import Symbol, Token, Tokenizer, QTerminal
from .utils import indent


class EBNFTerminalSymbol(Symbol):
    """Terminal Symbol for EBNFTokens"""
    is_terminal = True


class EBNFNonTerminalSymbol(Symbol):
    """Non-terminal symbol for EBNFTokens"""
    is_terminal = False


EBNFTokenizer = Tokenizer('')
EBNFTokenizer.add_lexer(r'\s+', None)
EBNFTokenizer.add_lexer('[a-z]+', 'RULE')
EBNFTokenizer.add_lexer('[A-Z]+', 'TERM')

EBNFTokenizer.add_lexer(r'"([^"]+)"', 'LITERAL')

EBNFTokenizer.add_lexer("[{]", 'STARTREPEAT')
EBNFTokenizer.add_lexer("[}]", 'ENDREPEAT')
EBNFTokenizer.add_lexer("[(]", 'STARTGROUP')
EBNFTokenizer.add_lexer("[)]", 'ENDGROUP')
EBNFTokenizer.add_lexer("[[]", 'STARTOPTIONAL')
EBNFTokenizer.add_lexer("[]]", 'ENDOPTIONAL')
EBNFTokenizer.add_lexer("[<]", 'STARTATL')
EBNFTokenizer.add_lexer("[>]", 'ENDATL')
EBNFTokenizer.add_lexer("[|]", 'OR')
EBNFTokenizer.add_lexer(":=", 'DEFINE')
EBNFTokenizer.add_lexer(";", 'ENDDEFINE')

STARTREPEAT = EBNFTokenizer.symbols['STARTREPEAT']
ENDREPEAT = EBNFTokenizer.symbols['ENDREPEAT']
STARTGROUP = EBNFTokenizer.symbols['STARTGROUP']
ENDGROUP = EBNFTokenizer.symbols['ENDGROUP']
STARTOPTION = EBNFTokenizer.symbols['STARTOPTIONAL']
ENDOPTION = EBNFTokenizer.symbols['ENDOPTIONAL']
STARTATL = EBNFTokenizer.symbols['STARTATL']
ENDATL = EBNFTokenizer.symbols['ENDATL']

OR = EBNFTokenizer.symbols['OR']
LITERAL = EBNFTokenizer.symbols['LITERAL']
RULE = EBNFTokenizer.symbols['RULE']
TERM = EBNFTokenizer.symbols['TERM']


REPEATING = EBNFNonTerminalSymbol('REPEATING')
SEQUENCE = EBNFNonTerminalSymbol('SEQUENCE')
OPTIONAL = EBNFNonTerminalSymbol('OPTIONAL')
OPT = EBNFTerminalSymbol('OPT')
REP = EBNFTerminalSymbol('REP')
ATL = EBNFTerminalSymbol('ATL')
ATLEASTONCE = EBNFNonTerminalSymbol('ATLEASTONCE')
ALTERNATING = EBNFNonTerminalSymbol('ALTERNATING')


class EBNFNode(object):
    """EBNFNode(token)
    EBNFNode stores a token and optional children of other EBNFNode
    objects to represent a single EBNF rule in a tree.
    """
    def __init__(self, token):
        self.token = token
        self.children = []

    @property
    def alternate(self):
        return self.token.symbol == ALTERNATING

    @property
    def optional(self):
        return self.token.symbol == OPTIONAL

    @property
    def repeating(self):
        return self.token.symbol == REPEATING

    @property
    def oneormore(self):
        return self.token.symbol == ATLEASTONCE

    def add(self, thing):
        """add a node to this node's children"""
        assert isinstance(thing, EBNFNode)
        self.children.append(thing)

    @property
    def key(self):
        """returns a code describing the node."""
        if self.children:
            res = []
            if self.repeating:
                res.append('rep')
            if self.optional:
                res.append('opt')
            if self.oneormore:
                res.append('atl')
            if self.alternate:
                res.append('alt')
            return ''.join(res) if res else 'seq'
        else:
            return 'trm'

    def __str__(self):
        return "{} <{}:{}>".format(self.__class__.__name__,
                                   self.key, self.token.lexeme)

    __repr__ = __str__


class EBNFToken(Token):
    pass


SEQ_MAP = {STARTGROUP: SEQUENCE, STARTREPEAT: REPEATING,
           STARTOPTION: OPTIONAL, STARTATL: ATLEASTONCE}
SUFFIX_MAP = {REP: REPEATING, OPT: OPTIONAL, ATL: ATLEASTONCE}

groupings = {STARTGROUP: ENDGROUP,
             STARTREPEAT: ENDREPEAT,
             STARTOPTION: ENDOPTION,
             STARTATL: ENDATL}

groupcount = Counter()


def make_parser_node(name, tokens, endtoken=None):
    """make_parser_node(name, tokens [,endtoken])
    Recursive method for taking a series of tokens representing one EBNF
    rule and returning a EBNFNode tree.

    This function is called by :class:`EBNFParser` automatically.
    """
    if not tokens:
        return None, []
    logging.debug("make_parser_node for '%s' with %d tokens", name, len(tokens))

    this = EBNFNode(EBNFToken(SEQUENCE, name, 0, 0))
    logging.debug("this is %x", id(this))

    while tokens:
        first = tokens[0]

        if first.symbol in [STARTGROUP, STARTREPEAT, STARTOPTION, STARTATL]:
            logging.debug("found %s in %x", first.symbol.name, id(this))
            key = name.split('-')[0]
            groupcount[key] += 1
            child, tokens = make_parser_node("%s-%d" % (key, groupcount[key]),
                                             tokens[1:],
                                             groupings[first.symbol])
            if child:
                child.token.symbol = SEQ_MAP[first.symbol]
                this.add(child)

        elif first.symbol in [ENDGROUP, ENDREPEAT, ENDOPTION, ENDATL]:
            logging.debug("Found %s with %d tokens left in %x",
                          first.symbol.name, len(tokens), id(this))
            if endtoken != first.symbol:
                raise SyntaxError("Expected %s to close group, got %s" %
                                  (endtoken.name, first.symbol.name))

            used_brackets = first.symbol in [ENDREPEAT, ENDOPTION]

            if len(tokens) > 1:
                if used_brackets and tokens[1].symbol in [REP, OPT, ATL]:
                    msg = "Illegal mix of brackets and suffixes in %s" % name
                    logging.error(msg)
                    raise SyntaxError(msg)

                if tokens[1].symbol in [REP, OPT, ATL]:
                    this.token.symbol = SUFFIX_MAP[tokens[1].symbol]
                    logging.debug("Changed %x to symbol %s",
                                  id(this), this.token.symbol)
                    tokens.pop(0)

            return this, tokens[1:]

        elif first.symbol == OR:
            logging.debug("Found or in %d with symbol %s",
                          id(this), this.token.symbol)
            # this.alternate = True
            this.token.symbol = ALTERNATING
            logging.debug("Changed %x to symbol %s",
                          id(this), this.token.symbol)
            this.add(EBNFNode(first))
            tokens.pop(0)

        else:
            this.add(EBNFNode(first))
            tokens.pop(0)

    logging.debug("Returning %x with %d tokens", id(this), len(tokens))
    return this, tokens


class CSTNode(object):
    """Concrete Syntax Tree Node.
    This node holds a token and a list of children for that token.
    """
    def __init__(self, token):
        self.token = token
        self.children = []

    def __str__(self):
        return "<CSTNode:{} >".format(self.token)


def print_cstnode(treenode, ind=0):
    """prints a CSTNode"""
    print("{0}< {1} >".format(indent(ind), treenode.token.lexeme))
    for child in treenode.children:
        print_cstnode(child, ind+2)


def lexemes(tokens):
    """Returns a string of token lexemes"""
    return '"{}"'.format(" ".join(t.lexeme for t in tokens))


def token_lexemes(tokens):
    """Returns a string of token lexemes for CSTNode lists"""
    return '"{}"'.format(" ".join(t.token.lexeme for t in tokens))


def split_by_or(iterable):
    """splits a list of EBNFTokens into separate lists defined by OR symbols"""
    return [list(g) for k, g in groupby(iterable,
                                        lambda x: x.token.symbol == OR)
            if not k]


__logic__ = """
match_sequence(list_of_expected_nodes, list_of_tokens)
    returns a (list_of_CSTNodes, list_of_remaining_tokens) or
    ([], list_of_tokens)

match_terminal(expected_node, list_of_tokens)

New idea: tertiary (and secondary) methods return a boolean if a match was made
or not

match_rule(rulename, list_of_tokens)
    match(parsernode, list_of_tokens)
        match_terminal(parsernode, list_of_tokens)
        match_non_terminal(parsernode, list_of_tokens)

"""


class EBNFParser(object):
    """
    Class to read EBNF text and return a dictionary of rules
    plus a dictionary of (name, Symbol) pairs
    """

    def __init__(self, text):
        self.symbol_table = {}
        self.start_rule = None
        self.collapse_tree = True
        self.token_class = Token
        logging.debug("EBNFParser.__init__() start")
        lines = [line for line in text.split(';') if line.strip()]
        data = [line.split(":=") for line in lines]
        self.rules = OrderedDict()
        self.tokenizer = Tokenizer('', self.token_class)
        self.tokenizer.add_lexer(r'\s+', None)
        self.tokenizer.add_lexer(r'"[^"]+"', 'LITERAL')
        kept_tokens = {}  # try to keep references to only one token
        for key, val in data:
            key = key.strip()
            if key in self.symbol_table:
                raise SyntaxError('rule for %s already exists' % key)

            if key.islower():
                ebnf_tokens = list(EBNFTokenizer(val))
                parser_node, remaining = make_parser_node(key, ebnf_tokens)
                if remaining:
                    logging.exception("rule %s did not process correctly", key)
                    raise SyntaxError("rule %s did not process correctly" % key)
                self.rules[key] = parser_node
                self.symbol_table[key] = EBNFNonTerminalSymbol(key)
            elif key.isupper():
                if self.tokenizer.symbols.get(key) is not None:
                    raise ValueError(
                            "Redefining terminal symbol %s in EBNF" % key)
                self.tokenizer.symbols[key] = QTerminal(key)
                self.tokenizer.add_lexer(val.strip(), key)
                self.symbol_table[key] = EBNFTerminalSymbol(key)

        self.start_rule = next(iter(self.rules.keys()))
        self.kept_tokens = kept_tokens
        logging.debug("EBNFParser.__init__() end")

        self._calls = Counter()
        self._report_list = []
        self._max_recursion_level = 0

    def _report(self, ind, *stuff):
        stuff_string = ' '.join(stuff)
        self._report_list.append("{}{}".format(indent(ind), stuff_string))

    def report(self):
        """Returns a report of the parsing process, using indents to indicate
        recursion levels"""
        for line in self._report_list:
            print(line)

    def parse_text(self, text):
        """parse_text(text)

        Parse the DSL text and return a CSTNode plus any uncoverted tokens
        """
        self._report_list = []
        self._max_recursion_level = 0
        self.tokenizer(text)
        tokens = list(self.tokenizer)
        # print("Parsing tokens:", tokens)
        return self.parse(tokens)

    def parse(self, tokens):
        """Parse tokens into an CSTNode tree"""
        if not self.start_rule:
            raise ValueError("no start rule established")
        return self.match_rule(self.start_rule, tokens)

    def match_rule(self, rule: str, tokens: list, i: int = 0):
        """Given a rule name and a list of tokens, return an
        CSTNode and remaining tokens
        """
        self._calls[rule] += 1
        parser_node = self.rules.get(rule)

        if parser_node is None:
            logging.exception("No rule for %s", rule)
            raise SyntaxError("No rule for {}".format(rule))

        self._report(i, "mr:trying rule", parser_node.token.lexeme,
                     token_lexemes(parser_node.children), lexemes(tokens))

        logging.debug("matching rule `%s` for %d tokens with %s",
                      rule, len(tokens), parser_node)

        if not isinstance(parser_node.token, EBNFToken):
            raise ValueError("parser node missing required EBNFToken")

        ok, node, tokens = self.match(parser_node, tokens, i+1)
        if i == 0 and tokens:
            logging.error("Not all input consumed")
            raise ValueError("not all input consumed %s" % tokens[:3])
        return ok, node, tokens

    def match(self, parser_node: EBNFNode, tokens: list, i: int):
        """match(parser_node, tokens [,i])
        Call either match_terminal or match_nonterminal if the parser_node's
        token is terminal or not.

        :return: tuple of (boolean, CSTNode or None, list)

        """
        if not (parser_node.optional or parser_node.repeating):
            if not tokens:
                raise SyntaxError(
                    "Unexpected end of tokens for %s" % parser_node)
        self._report(
            i,
            "m:match '%s' against '%s' with %d remaining" % (
                parser_node.token.lexeme, tokens[0].lexeme, len(tokens)))
        self._max_recursion_level = max(i, self._max_recursion_level)
        if parser_node.token.is_terminal:
            ok, res, tokens = self.match_terminal(parser_node, tokens, i)
        else:
            ok, res, tokens = self.match_nonterminal(parser_node, tokens, i)
        self._report(i, "m:match returning (%s, %s)" % (res, lexemes(tokens)))
        return ok, res, tokens

    def match_terminal(self, parser_node, tokens, i):
        self._calls['match_terminal'] += 1
        self._calls[parser_node.token.symbol.name] += 1

        logging.debug("matching terminal with %s for %d tokens",
                      parser_node, len(tokens))
        if not tokens:
            return False, None, tokens

        node = CSTNode(parser_node.token.lexeme)

        if parser_node.token.symbol == RULE:
            ok, child, tokens = self.match_rule(parser_node.token.lexeme,
                                                tokens, i+1)
            if child is not None:
                # collapse_tree shortens long descendencies with only one
                # child at the end
                if self.collapse_tree and len(child.children) == 1:
                    node.children.append(child.children[0])
                else:
                    node.children.append(child)
        elif parser_node.token.symbol == LITERAL:
            if parser_node.token.lexeme == tokens[0].lexeme:
                logging.debug("matching literal .. matched")
                self._report(i, "mt:ate literal", tokens[0].lexeme)
                node.children.append(CSTNode(tokens[0]))
                return True, node, tokens[1:]

            else:
                logging.debug("matching literal .. nope")
                return False, None, tokens
        elif parser_node.token.lexeme == tokens[0].symbol.name:
            logging.debug("matching symbol %s", parser_node.token.lexeme)
            self._report(i, "mt:ate terminal", tokens[0].lexeme)
            node.children.append(CSTNode(tokens[0]))
            return True, node, tokens[1:]
        else:
            logging.debug("did not match terminal %s", parser_node)
            return False, None, tokens
        return True, node, tokens

    def match_nonterminal(self, parser_node, tokens, i):
        self._calls[parser_node.token.symbol.name] += 1
        self._report(
            i,
            ("mnt:match_nonterminal '%s' with %d children "
             "against %d tokens") % (parser_node.token.lexeme,
                                     len(parser_node.children), len(tokens)))
        symbol = self.symbol_table[parser_node.token.lexeme.split('-')[0]]
        node = CSTNode(Token(symbol, parser_node.token.lexeme,
                             parser_node.token.start, parser_node.token.end))
        if not tokens:
            self._report(i,
                         "mnt:end of token stream. Current parser node is ",
                         parser_node.token.lexeme)
            return False, None, tokens

        child = None

        if parser_node.alternate:
            ok, child, tokens = self.match_alternate(parser_node, tokens, i+1)

        elif parser_node.repeating:
            logging.debug("Handle repeating elements (0 or more)")
            self._report(i, "mnt:Matching Repeating Element",
                         parser_node.token.lexeme)
            ok, child, tokens = self.match_repeating(parser_node, tokens, i+1)

        elif parser_node.optional:
            self._report(
                i,
                "mnt:matching optional:", token_lexemes(parser_node.children))
            ok, child, tokens = self.match_optional(parser_node, tokens, i+1)

        elif parser_node.oneormore:
            self._report(
                i, "mnt:matching atleast once:",
                token_lexemes(parser_node.children))
            ok, child, tokens = self.match_one_or_more(parser_node, tokens, i+1)
            if not ok:
                raise SyntaxError("Did not find required seqence at least once")

        elif parser_node.token.symbol == SEQUENCE:
            self._report(i, "mnt:Matching sequence:",
                         token_lexemes(parser_node.children))
            ok, found, tokens = self.match_sequence(parser_node.token.lexeme,
                                                    parser_node.children,
                                                    tokens, i+1)
            self._report(
                i,
                "mnt:matched sequence, extending with", token_lexemes(found))
            node.children.extend(found)

        else:
            self._report(i,
                         "mnt:ran out of options in match_nonterminal. error.")
            raise SyntaxError("ran out of options in match_nonterminal")

        if child is not None:
            self._report(
                i,
                "mnt:matched nonterminal, extending with",
                token_lexemes(child.children))
            node.children.extend(child.children)

        if node.children:
            return True, node, tokens
        else:
            return False, None, tokens

    def match_optional(self, parser_node, tokens, i):
        self._calls['match_optional'] += 1
        token = parser_node.token
        expected = parser_node.children
        node = CSTNode(token)
        self._report(i, "opt:match optional for", str(token))
        ok, children, tokens = self.match_sequence(
                token.lexeme, expected, tokens, i+1)
        if ok:
            node.children.extend(children)
            return True, node, tokens
        else:
            return False, None, tokens

    def match_one_or_more(self, parser_node, tokens, i):
        self._calls['match_one_or_more'] += 1
        token = parser_node.token
        expected = parser_node.children
        node = CSTNode(token)
        self._report(i, 'atl:match one or more for', str(token))
        ok, children, tokens = self.match_sequence(
                token.lexeme, expected, tokens, i+1)
        if not ok:
            raise SyntaxError("Missing group: %s" % tokens)
        while ok:
            node.children.extend(children)
            ok, children, tokens = self.match_sequence(
                token.lexeme, expected, tokens, i+1)
        if node.children:
            return True, node, tokens
        else:
            return False, None, tokens

    def match_repeating(self, parser_node, tokens, i):
        """matches the children of the parser node. Will match a full sequence
        in order and then try to match again.
        """
        self._calls['match_repeating'] += 1
        token = parser_node.token
        expected = parser_node.children
        node = CSTNode(token)
        logging.debug("match repeating")
        keep_trying = True
        while keep_trying:
            self._report(i, "rep:match repeating for", str(token))
            ok, addends, tokens = self.match_sequence(token.lexeme, expected,
                                                      tokens, i+1)
            self._report(i, "rep:from match_sequence:",
                         token_lexemes(addends), lexemes(tokens))
            if ok:
                node.children.extend(addends)
            else:
                keep_trying = False
                logging.debug("returning node with %d children",
                              len(node.children))

        if node.children:
            return True, node, tokens
        else:
            return False, None, tokens

    def match_alternate(self, parser_node, tokens, i):
        """EBNFNode is a node with OR in its children."""
        self._calls['match_alternate'] += 1
        logging.debug("match_alternate for %s", parser_node)
        if not tokens:
            return False, None, tokens

        alternates = split_by_or(parser_node.children)

        node = CSTNode(parser_node.token)

        original_tokens = list(tokens)
        for alternate in alternates:
            tokens = list(original_tokens)
            preview = tokens[0] if tokens else "No tokens"
            logging.debug("trying alternate: %s against %s",
                          token_lexemes(alternate), preview)
            self._report(i, "alt:trying alternate", token_lexemes(alternate))
            # Experiment 3/10
            try:
                ok, found, remaining_tokens = self.match_sequence(
                        parser_node.token.lexeme, alternate, tokens, i+1)
            except ValueError:
                logging.debug('alternate failed from value error')
                ok = False
            if ok:
                logging.debug("..got it!")
                self._report(i, "alt:matched alternate",
                             token_lexemes(alternate))
                node.children.extend(found)
                # print_cstnode(node, i+1)
                return True, node, remaining_tokens
            else:
                self._report(i, "did not match alternate",
                             token_lexemes(alternate))
                logging.debug("did not match alrternate")
        self._report(i, "alt:all alternates failed")
        return False, None, tokens

    def match_sequence(self, name, originals, tokens, i):
        """returns a list of CSTNodes and a list of remaining tokens"""
        self._calls['match_sequence'] += 1
        expected = list(originals)  # should create a copy
        orig_tokens = list(tokens)

        found = []

        while expected:
            this = expected[0]
            if not tokens:
                self._report(i,
                             "seq:sequence '%s' out of tokens, bailing" % name)
                if this.oneormore:
                    raise SyntaxError('Expected %s and found nothing' % this)
                # return False, found, tokens
                break
            self._report(
                    i,
                    "seq:expecting in '%s': '%s', got '%s'" % (
                        name, this.token.lexeme, tokens[0].lexeme))
            if tokens:
                logging.debug("expecting: %s got %s", this, tokens[0])
            else:
                logging.debug("expecing: %s with no tokens", this)
            ok, node, tokens = self.match(this, tokens, i+1)
            if node is not None:
                self._report(i, "seq:found", token_lexemes(node.children))
                found.extend(node.children)
            else:
                self._report(i, "seq:sequence failed on", this.token.lexeme)
                return False, found, tokens
            expected.pop(0)
            self._report(
                    i,
                    ('seq:end of sequence loop, '
                     'expecting: %s against %s' % (
                         token_lexemes(expected), lexemes(tokens))))

        if expected:
            return False, [], orig_tokens
        return ok, found, tokens
