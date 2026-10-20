# R10 pinned public-source acquisition

Data-only snapshots for the authorized R10 review. Retrieved source is never
imported, installed, compiled or executed. Batch manifests record exact requested
and final URLs, HTTP status, local acquisition time (not authenticated UTC), byte
lengths and SHA-256 of unchanged response bodies. The R10 report records source
anchors and correlation limitations. `acquire.py` is the local download helper,
not retrieved vendor code; it uses only the Python standard library.
