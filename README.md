outcade
=======

A tool to read holidays from Cascade and write them to an Exchange calendar


TODO:
 * Fix timezone
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
