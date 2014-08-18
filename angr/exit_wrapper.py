from itertools import dropwhile
import copy

import logging

l = logging.getLogger(name="angr.exit_wrapper")

class CallStack(object):
    def __init__(self, stack=None, retn_targets=None):
        if stack is None:
            self._stack = []
        else:
            self._stack = stack

        if retn_targets is None:
            self._retn_targets = []
        else:
            self._retn_targets = retn_targets

    def stack_suffix(self):
        length = len(self._stack)
        if length == 0:
            return (None, None)
        elif length == 1:
            return (None, self._stack[length - 1])
        return (self._stack[length - 2], self._stack[length - 1])

    def call(self, callsite_addr, addr, retn_target=None):
        self._stack.append(callsite_addr)
        self._stack.append(addr)
        self._retn_targets.append(retn_target)

    def current_func_addr(self):
        if len(self._stack) == 0:
            return 0 # This is the root level
        else:
            return self._stack[-1]

    def _rfind(self, lst, item):
        try:
            return dropwhile(lambda x: lst[x] != item, \
                             reversed(xrange(len(lst)))).next()
        except Exception:
            raise ValueError("%s not in the list" % item)

    def ret(self, retn_target):
        if retn_target in self._retn_targets:
            # We may want to return to several levels up there, not only a
            # single stack frame
            levels = len(self._retn_targets) - \
                self._rfind(self._retn_targets, retn_target)
        else:
            l.warning("Returning to unexpected address 0x%08x", retn_target)
            # For Debugging
            # raise Exception()
            # There are cases especially in ARM where return is used as a jump
            # So we don't pop anything out
            levels = 0
        while levels > 0:
            if len(self._stack) > 0:
                self._stack.pop()
                self._stack.pop()
            if len(self._retn_targets) > 0:
                self._retn_targets.pop()
            levels -= 1

    def get_ret_target(self):
        if len(self._retn_targets) == 0:
            return None
        return self._retn_targets[len(self._retn_targets) - 1]

    def copy(self):
        return CallStack(self._stack[::], self._retn_targets[::])

class BBLStack(object):
    def __init__(self, stack_dict=None):
        if stack_dict is None:
            self._stack_dict = {}
        else:
            self._stack_dict = stack_dict

    def copy(self):
        return BBLStack(copy.deepcopy(self._stack_dict))

    def call(self, addr):
        # Create a stack with respect to that function
        self._stack_dict[addr] = []

    def ret(self, addr):
        if addr in self._stack_dict:
            # Return from a function. Remove the corresponding stack
            del self._stack_dict[addr]
        else:
            l.warning("Attempting to ret from a non-existing stack frame %s." % str(addr))

    def push(self, func_addr, bbl):
        if func_addr not in self._stack_dict:
            l.warning("Key %s is not in stack dict. It might be caused by " + \
                      "an unexpected exit target.", func_addr)
            self.call(func_addr)
        self._stack_dict[func_addr].append(bbl)

    def in_stack(self, func_addr, bbl):
        if func_addr in self._stack_dict:
            return bbl in self._stack_dict[func_addr]
        return False

class SimExitWrapper(object):
    def __init__(self, ex, call_stack=None, bbl_stack=None):
        self._exit = ex
        if call_stack is None:
            self._call_stack = CallStack()

            # Added the function address of the current exit to callstack
            self._call_stack.call(None, self._exit.concretize())

            self._bbl_stack = BBLStack()
            # Initialize the BBL stack
            self._bbl_stack.call(self._call_stack.stack_suffix())
        else:
            self._call_stack = call_stack
            self._bbl_stack = bbl_stack
        assert(self._call_stack is not None and self._bbl_stack is not None)

    def sim_exit(self):
        return self._exit

    def call_stack(self):
        return self._call_stack

    def call_stack_copy(self):
        return self._call_stack.copy()

    def call_stack_suffix(self):
        return self._call_stack.stack_suffix()

    def bbl_stack_push(self, call_stack_suffix, bbl_addr):
        self._bbl_stack.push(call_stack_suffix, bbl_addr)

    def bbl_in_stack(self, call_stack_suffix, bbl_addr):
        return self._bbl_stack.in_stack(call_stack_suffix, bbl_addr)

    def bbl_stack(self):
        return self._bbl_stack

    def bbl_stack_copy(self):
        return self._bbl_stack.copy()

    def current_func_addr(self):
        return self._call_stack.current_func_addr()