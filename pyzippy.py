import python_minifier
import re
import urllib.parse
import zlib
import base64

r"""
URL Allowed:
(0-9), letters(A-Z, a-z), and a few special characters ( "-" , "." , "_" , "~")


Needed to replace: !@#$%^&*()[]{};:'",/`~\|=+<>?

Python Keywords: 
False await else import pass None break except in raise True
class finally is return and continue for lambda try as def
from nonlocal while assert del global not with async elif if or yield
"""

table = {
    "False": "A", "await": "a", "else": "B", "import": "b", "pass": "C", "None": "c", "break": "D", "except": "d",
    "in": "E", "raise": "e", "True": "F",
    "class": "f", "finally": "G", "is": "g", "return": "H", "and": "h", "continue": "I", "for": "i", "lambda": "J",
    "try": "j", "as": "K", "def": "k",
    "from": "L", "nonlocal": "l", "while": "M", "assert": "m", "del": "N", "global": "n", "not": "O", "with": "o",
    "async": "P", "elif": "p", "if": "Q", "or": "q", "yield": "R",

    "!": "r", "@": "S", "#": "s", "%": "t", "^": "U", "&": "u", "*": "V", "(": "v", ")": "W", "[": "w",
    "]": "X", "{": "x", "}": "Y", ";": "y", ":": "Z", "'": "z", "\"": "1", ",": "2", "/": "3", "`": "4",
    "\\": "6", "|": "7", "=": "8",
    "\n": "0",
    "\t": "T",
    " ": "9"
}
rev_table = {v: k for k, v in table.items()}

"""
The first character indicates whether compression is used or not.
If the original compressed string is over 1900 characters (by default), the string is compressed.
0 -> Compression is not used
1 -> Compression is Used

Ident:
Not everything can be compressed down into 1 symbol
So everything else that isnt in the table is labeled as `Ident`

`Ident` has the following format:
[1 char] 5 -> Identifier / Marker.  Never changes
[1 char] Length -> how many chars `ident` takes up.  In base 62 with 0 = 1 char in length, Z = 62 char in length
[var char] ident -> the actual name being contained 

There may be multiple `Ident` formats next to each other
"""

base_62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_kywds = re.compile("(" + "|".join(re.escape(x) for x in table.keys()) + ")")


def _form_ident(x: str):
    segments = []
    for s in range(0, len(x), 63):
        segment = x[s * 63:(s + 1) * 63]
        segments.append("5" + base_62[len(segment) - 1] + segment)
    return "".join(segments)


def _encode(txt: str, threshold_length: int = 1900):
    payload_string = ""
    for x in re.split(_kywds, txt):
        if x == "":
            continue
        if x in table:
            payload_string += table[x]
            continue
        payload_string += _form_ident(x)

    if len(payload_string) > threshold_length:
        encoded = "1" + base64.encodebytes(zlib.compress(payload_string.encode())).decode("ascii")
        # only return the zlib compression... if it actually compressed it
        return encoded if len(encoded) < len(payload_string) + 1 else "0" + payload_string
    return "0" + payload_string


def _decode(text: str):
    compression = text[0]
    text = text[1:]
    if compression == "1":
        text = zlib.decompress(base64.decodebytes(text.encode("ascii"))).decode()
    pointer = 0
    payload = ""
    while pointer < len(text):
        x = text[pointer]
        pointer += 1
        if x in rev_table:
            payload += rev_table[x]
            continue
        elif x != "5":
            raise ValueError(f"Invalid Symbol \"{x}\".  This symbol does not follow common procedure")
        length = base_62.index(text[pointer]) + 1
        pointer += 1
        payload += text[pointer:pointer + length]
        pointer += length
    return payload


def compress(code: str, *,
             url_safe: bool = True,
             threshold_length: int = 1900,
             remove_annotations: bool = True,
             remove_pass: bool = True,
             remove_literal_statements: bool = True,
             combine_imports: bool = True,
             hoist_literals: bool = True,
             rename_locals: bool = True,
             preserve_locals: list[str | bytes] | None = None,
             rename_globals: bool = ...,
             preserve_globals: list[str | bytes] | None = None,
             remove_object_base: bool = True,
             convert_posargs_to_args: bool = True,
             preserve_shebang: bool = False,
             remove_asserts: bool = False,
             remove_debug: bool = None) -> str:
    """Compress python code for smaller text size.  Best used for urls or other places where compression is needed.

    Example
    -------
    .. code-block:: python3
        code = '''
        import typing
        def add_values(vals: typing.List[int]) -> int:
        return sum(vals)
        values = add_values([1, 2, 3])
        print(add_values([values, 4, 5]))
        '''
        compressed = compress(code)
        print(len(code), len(compressed), compressed)
        # 148 94 0b952typE50g0k950Av53valsWZH952sumv53valsW050B850Avw50125022503XW051prE50tv50Avw50B25042505XWW
        # compress reduced the length of the code by 54 characters

    Parameters
    ----------
    code: :class:`str`
        The code to be encoded.
    url_safe: :class:`bool`
        Escape Base64 characters such as ``"+"``, ``"="``, and ``"/"``. ``True`` by default.
    threshold_length: :class:`int`
        The threshold for how how long the compressed string must be to call :func:``zlib.compress``.
        If the compression done by :func:``zlib.compress`` results in a longer string, the value is
        discarded and the previously compressed string is used. ``threshold_length`` is only used to prevent
        redundant work from being done.  If you want speedier compression with a potentially longer string, use
        a high value.  Default is ``1900`` characters in length.
    remove_annotations: :class:`bool`
        Used in the process for minifying code.  If ``code`` contains annotations that are necessary to the functionality
        at runtime, such as discord type annotations or dataclasses.dataclass annotations, disable this feature.
        ``True`` by default.
    remove_pass: :class:`bool`
        Used in the process for minifying code.  All ``pass`` keywords are replaced with a literal ``0``.
        ``True`` by default.
    remove_literal_statements: :class:`bool`
        Used in the process for minifying code.  All statements that only consist of literals, such as docstrings, will
        be replaced with ``0``.  ``True`` by default.
    combine_imports: :class:`bool`
        Used in the process for minifying code.  Combines multiple imports into one line.  ``True`` by default.
    hoist_literals: :class:`bool`
        Used in the process for minifying code.  If literal values are used multiple times, there will be new variables
        to remove duplicate literals.  ``True`` by default.
    rename_locals: :class:`bool`
        Used in the process for minifying code.  Shortens local names to increase compression size.
        If you wish to maintain a certain name in the code, see ``preserve_locals``.  ``True`` by default.
    preserve_locals: list[:class:`str` | :class:`bytes`] | None
        Used in the process for minifying code.  Maintains a list of certain names given within the list.
        If a value is within this list, the compressed code with maintain the name of the specified local
        variable.  By default, all values are renamed.
    rename_globals: :class:`bool`
        Used in the process for minifying code.  Shortens global names to increase compression size.
        If you wish to maintain a certain name in the code, see ``preserve_globals``.  ``True`` by default.
    preserve_globals: list[:class:`str` | :class:`bytes`] | None
        Used in the process for minifying code.  Maintains a list of certain names given within the list.
        If a value is within this list, the compressed code with maintain the name of the specified global
        variable.  By default, all values are renamed.
    remove_object_base: :class:`bool`
        Used in the process for minifying code.  Removes ``object`` from the inheritance of classes.
        ``True`` by default.
    convert_posargs_to_args: :class:`bool`
        Used in the process for minifying code.  Removes ``/`` from parameter list of functions.
        ``True`` by default.
    preserve_shebang: :class:`bool`
        Used in the process for minifying code.  Preserves ``#!/usr/bin/python`` at the top of
        code.  ``False`` by default.
    remove_asserts: :class:`bool`
        Used in the process for minifying code.  Removes ``assert`` statements within the code.
        Use this feature only if you know they are not needed.  ``False`` by default.
    remove_debug: :class:`bool`
        Used in the process for minifying code.  Removes ``if`` statements that contain
        comparisons to ``__debug__``.  Default is the opposite value of ``__debug__``.

    Returns
    -------
    :class:`str`
        A compressed version of ``code``

    Raises
    ------
    SyntaxError
        If the code was not parsed correctly

    See Also
    --------
    python_minifier : For more information on the minification process
    """
    remove_debug = not __debug__ if remove_debug is None else remove_debug
    minify = python_minifier.minify(code, None, remove_annotations, remove_pass, remove_literal_statements,
                                    combine_imports, hoist_literals, rename_locals, preserve_locals, rename_globals,
                                    preserve_globals, remove_object_base, convert_posargs_to_args, preserve_shebang,
                                    remove_asserts, remove_debug)

    compressed = _encode(minify, threshold_length=threshold_length)
    return urllib.parse.quote(compressed, safe="") if url_safe else compressed


def decompress(compressed_data: str) -> str:
    """Decompress code for saving or execution



    Parameters
    ----------
    compressed_data: :class:`str`
        The data that is compressed.  This compression must come from :func:`compress`.

    Returns
    -------
    :class:`str`
        The decompressed code

    See Also
    --------
    compress : for compression
    """
    string = urllib.parse.unquote(compressed_data)
    return _decode(string)