# Analytics ES — 2026-09-05

## ERRO
```
<HttpError 403 when requesting https://youtubeanalytics.googleapis.com/v2/reports?ids=channel%3D%3DMINE&startDate=2024-01-01&endDate=2026-09-05&metrics=estimatedMinutesWatched%2Cviews%2CaverageViewDuration&alt=json returned "Request had insufficient authentication scopes.". Details: "[{'message': 'Insufficient Permission', 'domain': 'global', 'reason': 'insufficientPermissions'}]">
```
Causa: token sem escopo yt-analytics.readonly
