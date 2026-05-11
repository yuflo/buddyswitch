# Project Source Mount Point

`projects/app` is a BuddySwitch runtime mount point for shared product source.

The BuddySwitch framework repository intentionally does not ship a concrete
sample app here. Launcher-managed product-mode instances project this path from
`${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app` into each runtime
workspace as relative `projects/app`.

Real product source belongs in the launcher-managed project workspace or in a
separate project repository, not as framework-bundled sample content.
