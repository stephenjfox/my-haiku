# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_Introducing_Initialization.ipynb.

# %% auto 0
__all__ = ['frame_stack', 'Frame', 'TransformedFunc', 'transform', 'get_param', 'Module', 'module_method', 'Linear']

# %% ../nbs/02_Introducing_Initialization.ipynb 4
from typing import NamedTuple, Dict, Callable
import numpy as np
import jax
import jax.numpy as jnp

# %% ../nbs/02_Introducing_Initialization.ipynb 5
frame_stack = []

class Frame(NamedTuple):
    """Tracks mechanery state during a call of a transformed function."""
    params: Dict[str, jnp.ndarray]
    is_initializing: bool = False

    @classmethod
    def current_frame(cls): return frame_stack[-1]

class TransformedFunc(NamedTuple):
    init: Callable # [[], jnp.ndarray]
    apply: Callable # [[Frame.params], jnp.ndarray]

def transform(f) -> TransformedFunc:

    def init_f(*args, **kwargs):
        frame_stack.append(
            Frame({}, is_initializing=True)
        )
        f(*args, **kwargs) # why do we invoke f? because it's a module?
        frame = frame_stack.pop()
        return frame.params

    def apply_f(params, *args, **kwargs):
        frame_stack.append(Frame(params))
        outputs = f(*args, **kwargs)
        frame_stack.pop()
        return outputs

    return TransformedFunc(init_f, apply_f)

def get_param(identifier, shape=None):
    """Get parameter according to `identifier`, initializing with `shape` if necessary.

    Improvement over the tutorial code: we don't fall to race conditions. I know Pythonistas aren't
    generally concerned with that (what with the language being single-threaded and all) but it's a
    good thing to note: when you're modifying someting that's supposed to be atomic, you best make
    changes while you've got the thing. Never know if you're going to lose your grip.

    Args:
        identifier:
            valid str to identify the parameter
        shape (optional):
            MUST BE INCLUDED IF YOUR PARAMETER IS NOT YET INITIALIZED.
            ignored if the parameter has already been instantiated.
    """
    if (top_frame := Frame.current_frame()).is_initializing:
        top_frame.params[identifier] = np.random.normal(size=shape)

    return top_frame.params[identifier]

# %% ../nbs/02_Introducing_Initialization.ipynb 9
import dataclasses, collections

# %% ../nbs/02_Introducing_Initialization.ipynb 10
@dataclasses.dataclass
class Frame:
    """Tracks what's going on during a call of a transformed function"""
    params: Dict[str, jnp.ndarray]
    is_initializing: bool = False

    """Keeps track of how many modules of each class have been created so far.
    Used to assign new modules unique names"""
    module_counts: Dict[str, int] = dataclasses.field(default_factory=collections.Counter)

    """Keeps track of the entire path to the current module method call.
    Module methods will add themselves to this stack when called.
    Used to give each parameter a unique name corresponding to stack location.
    """
    call_stack: list = dataclasses.field(default_factory=list)

    def create_param_path(self, identifier) -> str:
        """Creates a unique path for param identified by `identifier`"""
        return "/".join(["~"] + self.call_stack + [identifier])

    def create_unique_module_name(self, module_name: str) -> str:
        """creates a unique name to identify this module, by attending its instance count to its name"""
        number = self.module_counts[module_name]
        self.module_counts[module_name] += 1
        # concerns with this state modification:
        # 1. it only refers to this Frame, not all some communal global state
        # 2. create and updating don't have to be separate, but it can ease some thinking.
        return f"{module_name}_{number}"

    @classmethod
    @property
    def current(cls):
        "Current frame on the frame stack"
        return frame_stack[-1] if frame_stack else None

"global state for tracking frames"
frame_stack = []

# %% ../nbs/02_Introducing_Initialization.ipynb 14
class Module:
    def __init__(self):
        "Assign a unique name for instance of this module for the given `transform` call"
        self._unique_name = Frame.current.create_unique_module_name(
            self.__class__.__name__)

def module_method(f):
    """Decorate a Module method

    In the real Haiku, the user wouldn't see this, as it's handled by the metaclass"""
    def wrapped(self, *args, **kwargs):
        """A version of f that gives us some call stack information"""
        module_name = self._unique_name
        f_name = f.__name__

        call_stack = Frame.current.call_stack
        call_stack.append(module_name)
        call_stack.append(f_name)
        outputs = f(self, *args, **kwargs)
        assert call_stack.pop() == f_name
        assert call_stack.pop() == module_name
        return outputs

    return wrapped

def get_param(identifier, shape=()):
    frame = Frame.current
    param_path = frame.create_param_path(identifier)
    if frame.is_initializing:
        frame.params[param_path] = np.random.normal(size=shape)

    return frame.params[param_path]

class Linear(Module):
    def __init__(self, width):
        super().__init__()
        self._width = width

    @module_method
    def __call__(self, x):
        # same as before
        W = get_param('W', shape=(x.shape[-1], self._width))
        b = get_param('b', shape=(self._width,))
        return x @ W + b
