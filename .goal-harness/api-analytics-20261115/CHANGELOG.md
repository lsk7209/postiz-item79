# Changes

- Enabled youtubeanalytics.googleapis.com only in postiz-item79.
- Added web-only exact-channel analytics helper shared by private/public routes, saved-grant refresh, separate 5min cache and safe typed errors.
- Replaced empty-result OAuth redirect with API retry and honest no-data/error message; added views and correct seconds for duration.
- Added analytics and narrowly pinned web release-policy tests; Dockerfile copies exact web source paths only. Shared worker source unchanged.
