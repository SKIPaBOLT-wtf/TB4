# DEF-042 fixture repair source

Source `37f8c9cc1d9487edea98e7ae26b7df294a8a55ac`, repair INTENT0007. Only new test import/support
composition changed. Qualified Windows fixture ACL helper, actual native_settings
and native credential pair remain; POSIX file protection uses fresh fixture modes.
The local fixed credential probe is bound to the current synthetic approved device
instead of reusing another fixture's constant device. It never executes a command.
No product/earlier test change or test result is claimed here. Dedicated collection
and all original focused assertions must pass before resolving DEF042.
