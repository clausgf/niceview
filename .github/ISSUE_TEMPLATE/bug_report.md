---
name: Bug report
about: Report something that doesn't work as expected
title: ''
labels: bug
assignees: ''
---

**Describe the bug**
A clear and concise description of what the bug is.

**Minimal reproducer**
A small Pydantic model plus the NiceView call that triggers it:

```python
import pydantic
from niceview import ModelForm

class M(pydantic.BaseModel):
    ...

# ...
```

**Expected behavior**
What you expected to happen.

**Actual behavior**
What happened instead (include the full traceback if there is one).

**Environment**
- NiceView version:
- NiceGUI version:
- Python version:
- OS:
