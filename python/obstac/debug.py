import sys, traceback
from inspect import stack, getmodule
import inspect
from obstac import logger

DO_DEBUG = __debug__

def logger_debug(*args, **kwargs):
    logger.debug(*args, **kwargs)

def set_debug(debug_state):
    global DO_DEBUG
    DO_DEBUG = debug_state

def set_debug_out(debug_out):
    global logger_debug
    logger_debug = debug_out

def debug(text,*args):
    if text is not None:
        text = text.replace("\n","\\n")
    if DO_DEBUG:
        logger_debug(text)
    
