"""Tools for reading SDSS FTCL / Yanny par files in Python

:Authors: Eric H. Neilsen, Jr.
:Contact: <neilsen@fnal.gov>
:Date: 2010-06-23
:Version: v0_1
:Organization: Fermi National Accelerator Laboratory

Information on Yanny par files is described on the `FTCL <http://das.sdss.org/www/html/dm/flatFiles/yanny.html>`_.

These tools are built on the `pyparsing <http://pyparsing.wikispaces.com/>`_.

>>> r = YannyReader(url='http://das.sdss.org/nightly/53436/mdReport-53436.par')
>>> # If you have a local file, use "file_name=" instead of "url="
>>>
>>> # List all header keywords
>>> print r.header.keys()
['mjd', 'ccdConfig', 'ccdBC', 'parametersDir', 'telescope', 'parameters', 'ccdVoltages', 'ccdECalib', 'version', 'authors', 'fileNameFormat', 'equinox', 'configDir']
>>>
>>> # Read a header value
>>> print r.header['telescope']
APO20
>>>
>>> # List the chains in the file
>>> print r.struct.keys()
['EXP', 'MTCOMMENT']
>>>
>>> # Count the number of entries for each type
>>> for s in r.struct.keys():
...     print "%s: %d" % (s, len(r.read_chain(s)))
EXP: 233
MTCOMMENT: 7
>>>
>>> # Read a few isolated values from chains
>>> exposures = r.read_chain('EXP')
>>> print exposures[2]['mjd']
53435.93408
>>> print exposures[2]['targetName']
Bias
>>>
>>> # Count the number of primary exposures this night
>>> pri_exp_times = [x['expTime'] for x in exposures if x['flavor']=='Pri']
>>> print len(pri_exp_times)
155
>>> # Get the total exposure time spent on primaries this night
>>> print sum(pri_exp_times)
4974.0
"""
__docformat__ = "restructuredtext en"

import urllib2
from string import translate

from pyparsing import Forward
from pyparsing import LineStart, LineEnd
from pyparsing import Keyword, CaselessKeyword, Literal, Word, QuotedString, quotedString, nestedExpr, White
from pyparsing import alphas, nums, alphanums, printables, CharsNotIn
from pyparsing import Optional, And, Or, Combine, NotAny, Regex
from pyparsing import Group, OneOrMore, ZeroOrMore, oneOf, delimitedList
from pyparsing import cStyleComment, restOfLine, lineEnd
from pyparsing import removeQuotes, stringEnd
from pyparsing import Dict

hash_comment = Literal("#") + restOfLine
semicolon = Literal(";").suppress()
comma = Literal(",").suppress()
left_brace = Literal("{").suppress()
right_brace = Literal("}").suppress()
possible_type_name = Word(alphas, alphanums+'_')
value_name = Word(alphas, alphanums+'_')
field_name = Word(alphas, alphanums+'_')
enum_declaration_start = Literal('typedef enum') 
struct_declaration_start = Literal('typedef struct') 

# Some old SDSS par files leave spaces between a \ and a newline, even
# when it is intended to be a line continuation, so we need to deal with it
linecont = Optional(Regex('\\\ *\n'))
length_spec = Optional(nestedExpr("[","]") | nestedExpr("<",">")).suppress()

numsign = oneOf('+ -')
integer = Combine(Optional(numsign) + Word( nums ))
integer.setParseAction( lambda s,l,t: int(t[0]) )

decimal = Combine( Optional(numsign) + Word(nums) + Optional(Literal('.') + Word(nums)) \
                       + Optional( oneOf('e E') + Optional(numsign) + Word(nums) ) )
decimal.setParseAction( lambda s,l,t: float(t[0]) )

nbprintables = translate(printables,None,'{}')
string = Or([QuotedString("'", escChar='\\', multiline=True),
             QuotedString('"', escChar='\\', multiline=True),
             Word(nbprintables) ])
string.setParseAction( lambda s,l,t: str(t[0]) )

braced_string = Forward()
braced_string = OneOrMore(nestedExpr("{","}",content=braced_string) | string )
braced_string.setParseAction( lambda s,l,t: t)

decimal_list = nestedExpr("{","}",content=decimal)
decimal_list.setParseAction( lambda s,l,t: t.asList()[0] if len(t[0])==1 else t.asList() )
integer_list = nestedExpr("{","}",content=integer)
integer_list.setParseAction( lambda s,l,t: t.asList()[0] if len(t[0])==1 else t.asList() )
string_list = nestedExpr("{","}",content=braced_string)
string_list.setParseAction( lambda s,l,t: t.asList()[0] if len(t[0])==1 else t.asList() )

base_type_parsers = { 'char':  string | string_list,
                      'float': decimal | decimal_list,
                      'double': decimal | decimal_list,
                      'long': integer | integer_list,
                      'short': integer | integer_list,
                      'int': integer | integer_list
                      }

def make_one_enum_def_parser():
    """Create a parser that can parse one enum definition

    @return: a pyparsing parser that can parse an enum definition

    >>> test_parser = make_one_enum_def_parser()
    >>> test_string = \"""typedef enum {
    ...         START,
    ...         END
    ... } RUNMARK;\"""
    >>> parsed_string = test_parser.parseString(test_string)
    >>> print parsed_string['enum_name']
    RUNMARK
    >>> print parsed_string['values'].asList()
    ['START', 'END']
    """
    type_values = Word(alphas, alphanums+'_')
    value_list = Group( delimitedList(type_values) )
    
    one_enum_def_parser = enum_declaration_start + left_brace + value_list('values') \
        + right_brace + possible_type_name('enum_name') + semicolon
    
    return one_enum_def_parser

def parse_enum_defs(s, parsers=None):
    """Parse all of the enum defs in a string, and add them to a list of type parsers

    :Parameters:
        - `s`: the string to parse
        - `parsers`: the dictionary of parsers to which the new ones will be added (optional)

    @return: a list of parsers for parsing type declarations

    >>> test_string = \"""# A sample file
    ... a foo
    ... bar baz
    ...
    ... typedef enum { # a comment
    ...         START, /* another comment */
    ...         END
    ... } RUNMARK;
    ...
    ... typedef struct { 
    ...         float x; 
    ...         int y
    ... } GOO
    ...
    ... typedef enum {
    ...         OAK,
    ...         MAPLE
    ... } TREES;
    ...
    ... GOO 3.4 6
    ... \"""
    >>> parsed_defs = parse_enum_defs(test_string)
    >>> runmark_parser = parsed_defs['RUNMARK']
    >>> runmark_parser.parseString("START")[0]
    'START'
    >>> runmark_parser.parseString("END")[0]
    'END'
    >>> try:
    ...    runmark_parser.parseString("41")[0]
    ... except:
    ...    print "parser threw an exception"
    parser threw an exception
    >>>
    >>> tree_parser = parsed_defs['TREES']
    >>> tree_parser.parseString("MAPLE")[0]
    'MAPLE'
    """
    type_parser = {} if parsers is None else parsers
    one_enum_def_parser = make_one_enum_def_parser()
    not_enum = ( (value_name | struct_declaration_start | possible_type_name | right_brace) + restOfLine).suppress()
    
    enum_def_parser = ZeroOrMore( Group(one_enum_def_parser) | not_enum ) + stringEnd
    enum_def_parser.ignore(hash_comment)
    enum_def_parser.ignore(cStyleComment)
    
    for enum in enum_def_parser.parseString(s):
        type_parser[enum['enum_name']] = oneOf( enum['values'].asList() )

    return type_parser


def make_one_struct_def_parser(type_parsers = None):
    """Create a parser that can parse one struct definition

    :Parameters:
        - `type_parsers`: (optional) a list of parsers that can parse declarations of the various types

    type_parsers defaults to parsers for the base types

    @return: a pyparsing parser that can parse a struct definition

    >>> test_parser =  make_one_struct_def_parser()
    >>> test_string = \"""typedef struct {
    ...  double mjd;
    ...  double humidity;
    ...  double pressure;
    ...  double temperature[4];
    ... } WEATHER;\"""
    >>> parsed_string = test_parser.parseString(test_string)
    >>> print parsed_string['struct_name']
    WEATHER
    >>> for f in parsed_string['fields']:
    ...   print "Field name: %-15s type name: %s" % (f['field_name'], f['type_name'])
    ... 
    Field name: mjd             type name: double
    Field name: humidity        type name: double
    Field name: pressure        type name: double
    Field name: temperature     type name: double
    >>>
    """
    if type_parsers is None:
        type_parsers = base_type_parsers
    type_name = oneOf( type_parsers.keys() )
    pafn = Combine(field_name + length_spec + length_spec)
    field_declaration = Group( type_name('type_name') + pafn('field_name') )
    field_list = Group( delimitedList(field_declaration, delim=';') )
        
    one_struct_def_parser = struct_declaration_start \
        + left_brace + field_list('fields') + Optional(semicolon) \
        + right_brace + possible_type_name('struct_name') + Optional(semicolon).suppress()
    
    return one_struct_def_parser

def parse_struct_defs(s, type_parsers = None):
    """Parse all the structure definitions in a string
    
    :Parameters:
        - `s`: the string to parse
        - `type_parsers`: a list of type parsers that can be used

    @return: a tuple with two dictionaries, one that describes the structs, the other stores the parsers

    >>> test_string = \"""# A sample file
    ... a foo
    ... bar baz
    ...
    ... typedef struct { # a comment
    ...         float x; /* another comment */
    ...         int y
    ... } GOO
    ...
    ... typedef enum {
    ...         START,
    ...         END
    ... } RUNMARK;
    ...
    ... typedef struct {
    ...         int i;
    ...         RUNMARK m
    ... } MOO;
    ...
    ... GOO 3.4 6
    ... \"""
    >>>
    >>> type_parsers = parse_enum_defs(test_string, base_type_parsers)
    >>> structs, struct_parsers = parse_struct_defs(test_string, type_parsers)
    >>>
    >>> print structs.keys()
    ['GOO', 'MOO']
    >>>
    >>> print struct_parsers.keys()
    ['GOO', 'MOO']
    >>>
    >>> for f in structs['GOO']:
    ...   print "Field name: %-15s type name: %s" % (f['field_name'], f['type_name'])
    Field name: x               type name: float
    Field name: y               type name: int
    >>>
    >>> for f in structs['MOO']:
    ...   print "Field name: %-15s type name: %s" % (f['field_name'], f['type_name'])
    Field name: i               type name: int
    Field name: m               type name: RUNMARK
    >>>
    >>> test_goo = "GOO 3.14 42"
    >>> test_parsed_goo = struct_parsers['GOO'].parseString(test_goo)
    >>> print "x: %f y: %d" % (test_parsed_goo[0]['x'], test_parsed_goo[0]['y'])
    x: 3.140000 y: 42
    >>>
    >>> test_moo = "MOO 44 END"
    >>> test_parsed_moo = struct_parsers['MOO'].parseString(test_moo)
    >>> print "i: %d m: %s" % (test_parsed_moo[0]['i'], test_parsed_moo[0]['m'])
    i: 44 m: END
    """
    if type_parsers is None:
        type_parsers = base_type_parsers
    
    one_struct_def_parser = make_one_struct_def_parser(type_parsers)
    not_struct = ( (value_name | enum_declaration_start | possible_type_name | right_brace) + restOfLine).suppress()
    
    struct_def_parser = ZeroOrMore( Group(one_struct_def_parser) | not_struct) + stringEnd
    struct_def_parser.ignore(hash_comment)
    struct_def_parser.ignore(cStyleComment)
    
    struct = {}
    struct_parser = {}
    for this_struct in struct_def_parser.parseString(s):
        struct_name = this_struct['struct_name'].upper()
        struct[struct_name] = \
            [{'field_name': f['field_name'], 'type_name': f['type_name']} for f in this_struct['fields']]
        struct_parser[struct_name] = \
            Group(CaselessKeyword(this_struct['struct_name']) \
                      + And( [linecont+type_parsers[f['type_name']](f['field_name']) 
                              for f in this_struct['fields']] ))

    return struct, struct_parser

def make_one_header_assignment_parser(struct_parsers):
    """Create a parser that can parse a single header assignment

    :Parameters:
        - `struct_parsers`: a dictionary of parsers for structs

    @return: a parser that can parse on header assignment

    >>> test_parser = make_one_header_assignment_parser({})
    >>>
    >>> test_string = "a 42 32"
    >>> parsed_assignments = test_parser.parseString(test_string)
    >>> print parsed_assignments[0]['name']
    a
    >>> print parsed_assignments[0]['value']
     42 32
    """
    all_struct_parsers = Or([struct_parsers[s] for s in struct_parsers.keys()] )
    one_header_assignment_parser = NotAny(all_struct_parsers) + Group(value_name('name') + restOfLine('value')) 
    one_header_assignment_parser.ignore(hash_comment)
    return one_header_assignment_parser

def parse_header(s, enum_def_parser, struct_def_parser, struct_parsers):
    """Create a dictionary of keyword assignments in a yanny par file

    :Parameters:
        - `s`: the string to parse
        - `enum_def_parser`: a parser that parses one enum definition
        - `struct_def_parser`: a parser that parses on struct definition
        - `struct_parsers`: a dictionary of structures that parse structure data

    @return: a dictionary with the keyword assignments

    >>> test_string = \"""# A sample file
    ... a foo
    ... bar baz goo # no more
    ...
    ... typedef enum {
    ...         START,
    ...         END
    ... } RUNMARK;
    ...
    ... typedef struct {
    ...         float x;
    ...         int y
    ... } GOO
    ...
    ... typedef enum {
    ...         OAK,
    ...         MAPLE
    ... } TREES;
    ...
    ... GOO 3.4 6
    ... \"""
    >>> 
    >>> enum_def_parser = make_one_enum_def_parser()
    >>> type_parsers = parse_enum_defs(test_string, base_type_parsers)
    >>> struct_def_parser = make_one_struct_def_parser(type_parsers)
    >>> structs, struct_parsers = parse_struct_defs(test_string, type_parsers)
    >>> h = parse_header(test_string, enum_def_parser, struct_def_parser, struct_parsers)
    >>> print h['a']
    foo
    >>> print h['bar']
    baz goo
    """
    one_header_assignment_parser = make_one_header_assignment_parser(struct_parsers)
    not_header = Or([enum_def_parser, struct_def_parser] + \
                        [struct_parsers[k] for k in struct_parsers.keys()]).suppress()
    
    header_parser = ZeroOrMore(not_header | one_header_assignment_parser) + stringEnd
    header_parser.ignore(hash_comment)
    header_parser.ignore(cStyleComment)
    header = {}
    for d in header_parser.parseString(s):
        header[d['name']] = d['value'].partition('#')[0].lstrip().rstrip()

    return header

def read_chain(s, struct_name, enum_def_parser, struct_def_parser, header_assignment_parser, struct_parsers):
    """Return a list of dictionaries with the contents of structures in a Yanny par file.

    :Parameters:
        - `s`: the string to parse
        - `struct_name`: the name of the struct to extract
        - `enum_def_parser`: a parser that parses one enum definition
        - `struct_def_parser`: a parser that parses on struct definition
        - `header_assignment_parser`: a parser that parses header assignments
        - `struct_parsers`: a dictionary of structures that parse structure data

    @return: a list of dictionaries with the contents of a chain

    >>> test_string = \"""# A sample file
    ... a foo
    ... bar baz
    ...
    ... typedef enum {
    ...         OAK,
    ...         MAPLE
    ... } TREETYPE;
    ...
    ... typedef struct {
    ...         float x;
    ...         int y
    ... } GOO
    ...
    ... typedef struct {
    ...         int i;
    ...         TREETYPE s
    ... } TREE;
    ...
    ... GOO 3.4 6
    ... TREE 42 MAPLE
    ... TREE 44 OAK
    ... TREE 3 MAPLE
    ... GOO 4.22 103
    ... \"""
    >>> 
    >>> enum_def_parser = make_one_enum_def_parser()
    >>> type_parsers = parse_enum_defs(test_string, base_type_parsers)
    >>> struct_def_parser = make_one_struct_def_parser(type_parsers)
    >>> structs, struct_parsers = parse_struct_defs(test_string, type_parsers)
    >>> header_assignment_parser = make_one_header_assignment_parser(struct_parsers)
    >>> trees = read_chain(test_string, 'TREE',
    ...   enum_def_parser, struct_def_parser, header_assignment_parser, struct_parsers)
    >>> print len(trees)
    3
    >>> print trees[1]['i']
    44
    >>> print trees[2]['s']
    MAPLE
    """
    struct_name = struct_name.upper()
    other_list_parsers = [struct_parsers[sn]
                          for sn in struct_parsers.keys() 
                          if not sn == struct_name]            
    not_this_list_parser = Or( other_list_parsers + 
                               [enum_def_parser, 
                                header_assignment_parser,                                        
                                struct_def_parser] ).suppress()
    this_list_parser = ZeroOrMore(not_this_list_parser | struct_parsers[struct_name] ) + stringEnd
    this_list_parser.ignore(hash_comment)
    this_list_parser.ignore(cStyleComment)
    raw_results = this_list_parser.parseString(s)
    
    results = []
    for row_result in raw_results:
        dict_result = {}
        for field, value in row_result.items():
            dict_result[field]=value
        results.append(dict_result)
        
    return results


class YannyReader(object):

    def __init__(self, string=None, file_name=None, url=None):
        if not string is None:
            self.s = string
        elif not file_name is None:
            self.s = open(file_name,'r').read()
        elif not url is None:
            self.s = urllib2.urlopen(url).read()
        self.one_enum_def_parser = make_one_enum_def_parser()
        self.type_parser = parse_enum_defs(self.s, base_type_parsers)
        self.one_struct_def_parser = make_one_struct_def_parser(self.type_parser)
        self.struct, self.struct_parser = parse_struct_defs(self.s, self.type_parser)
        self.one_header_assignment_parser = make_one_header_assignment_parser(self.struct_parser)
        self.header = parse_header(self.s, self.one_enum_def_parser, self.one_struct_def_parser,
                                   self.struct_parser)

    def read_chain(self, struct_name):
        return read_chain(self.s, struct_name, self.one_enum_def_parser, self.one_struct_def_parser,
                          self.one_header_assignment_parser, self.struct_parser)

if __name__=='__main__':
    import doctest, sys
    doctest.testmod(sys.modules[__name__])

