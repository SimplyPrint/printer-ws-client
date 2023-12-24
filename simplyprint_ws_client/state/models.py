from typing import Optional, Union
from traitlets import Any, HasTraits, Integer, Unicode

class MaterialModel(HasTraits):
    type: Optional[Union[str, int]] = Any(None, allow_none=True)
    color: Optional[str] = Unicode(None, allow_none=True)
    hex: Optional[str] = Unicode(None, allow_none=True)
    ext: Optional[int] = Integer(None, allow_none=True)