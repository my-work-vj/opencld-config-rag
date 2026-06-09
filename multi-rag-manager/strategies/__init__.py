"""Strategy: automatically import all submodules so decorators fire."""

from . import ingestion   # noqa: F401
from . import chunking    # noqa: F401
from . import embedding   # noqa: F401
from . import indexing    # noqa: F401
from . import retrieval   # noqa: F401
from . import reranking   # noqa: F401
from . import response    # noqa: F401
