class PopError(Exception):    """This error indicates that a POP instruction was sent to an empty stack.""" class RunTimeError(Exception):    """Error during program execution"""    class RuleNameError(Exception):    """This error indicates a problem with a rule name in the library."""class FunctionNameError(Exception):    """This error indicates a problem with the function name in a library export"""class CallerError(Exception):    """There was a problem with the caller when adding or exporting a rule"""   ### These are Language Initiation Errorsclass LanguageError(Exception):    """This indicates a problem handling a feature of the Language class"""class MatchError(Exception):    """This error indicates that a match argument is neither a list nor a tuple"""class StringError(Exception):    """This error indicates that a string object was expected but not found"""    class DuplicateWordError(Exception):    """This error indicates that a previously declared match word was used"""class SpaceError(Exception):    """This error indicates that a string contains non-buffering spaces when it shouldn't"""class EmptyError(Exception):    """This error indicates that a function parameter was empty. This is a required string"""### These are Compiler Errorsclass BadLanguageError(Exception):    """This error indicates that StackCompiler or StackRunner was passed a parameter that is not a subclass of the StackLanguage class"""    class BadTextError(Exception):    """This error indicates that StackCompiler's text parameter is not a string object"""class NoSourceError(Exception):    """This error indicates that the comile command was called with no text to process"""    class DuplicateLabelError(Exception):     """This error indicates that the same label has been used twice"""    class LabelMisuseError(Exception):     """This error indicates that a label is being referred to as a register"""class MissingLabelError(Exception):    """This error indicates that a label is referenced without being declared"""    class FormattingError(Exception):     """This error indicates that an instruction follows a label on the same line, or no label appears right before a colon"""class KeywordMisuseError(Exception):    """This error indicates that a keyword is being used to store a value"""    class UnresolvedTokenError(Exception):    """This error indicates that the program listing refers to a register before it finds a storage reference to that register"""class UnresolvedReferenceError(Exception):    """This error indicates that a reference is not resolving. (Microsoft-level uselessness, I know)"""### These are Run-Time Errorsclass BadInstructionNumber(Exception):    """This error indicates that StackRunner was told to read an instruction not in the program"""    class MissingMethod(Exception):    """This error indicates that StackRunner is trying to call a class method that has not been written"""class LibraryError(Exception):    """This error indicates that an Import Command failed."""class LibraryImportError(Exception):    """This error indicates that while importing a library a method was overwritten"""    