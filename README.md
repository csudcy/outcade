outcade
=======

A tool to read holidays from Cascade and write them to an Exchange calendar


TODO:
 * Deal with updates (e.g. request being authorised)
 * Mark all events as deleted/updated
 * About page
 * Deal with other scenarios
  * What happens when there's a !
  * What happens if there's a combination on the same day?
 * Email sync fail to user
 * Email exceptions to me
 * Record User.*_last_successful_sync_datetime ?
 * Make a base sync service
 * Move settings to config
 * Refactor app.py into several structured files/directories
 * Disconnect Outcade users from Outlook users?
  * Users can enter their own exchange & cascade details?


DONE:
 * Pull events from Cascade
 * Push events to Exchange
 * Encrypt user passwords
 * Version database
 * Run tasks from cli
 * Allow non-admins to edit their own details on main page
 * Make user form error nicely on password errors
 * Periodically run syncs (heroku-scheduler?)
 * Show user upcoming holidays on main page
 * Time how long tasks take
 * Show last sync status and age on main page
 * Move TIP bar to the bottom & always show
 * Randomise TIPs
 * User sync enable/disable
 * Sync in single shot
 * Sync more months
 * Am vs pm
 * Holiday vs bank holiday
 * Calendar view on main page
