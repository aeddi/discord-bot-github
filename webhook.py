#!/usr/bin/env python
import os, sys, json, logging, requests
from enum import Enum
from logging.handlers import RotatingFileHandler
from discord_webhook import DiscordWebhook, DiscordEmbed

### Rotating logs consts
log_path = os.getenv('LOG_PATH', '/tmp/discord-webhook-logs')
max_logfile_bytes = 42 * 1024 * 1024 # 42MB
max_logfile_archives = 5

### Webhook URL consts
github_external = os.getenv('DISCORD_WEBHOOK_EXTERNAL')
github_staff = os.getenv('DISCORD_WEBHOOK_STAFF')

### Github token for cheking author permission (staff or external)
### This token needs 'public_repo' scope (or 'repo' for private repos)
github_api_token = os.getenv('GITHUB_API_TOKEN')

### Enum of relevant event types (not exhaustive)
class EventType(Enum):
    UNKNOWN                   = 0
    COMMIT_COMMENT            = 1
    ISSUE_COMMENT_CREATED     = 2
    ISSUE_COMMENT_EDITED      = 3
    ISSUE_COMMENT_DELETED     = 4
    ISSUE_OPENED              = 5
    ISSUE_EDITED              = 6
    ISSUE_DELETED             = 7
    ISSUE_PINNED              = 8
    ISSUE_UNPINNED            = 9
    ISSUE_CLOSED              = 10
    ISSUE_REOPENED            = 11
    ISSUE_ASSIGNED            = 12
    ISSUE_UNASSIGNED          = 13
    ISSUE_LABELED             = 14
    ISSUE_UNLABELED           = 15
    ISSUE_LOCKED              = 16
    ISSUE_UNLOCKED            = 17
    ISSUE_TRANSFERRED         = 18
    ISSUE_MILESTONED          = 19
    ISSUE_DEMILESTONED        = 20
    PR_OPENED                 = 21
    PR_CLOSED                 = 22
    PR_REOPENED               = 23
    PR_EDITED                 = 24
    PR_ASSIGNED               = 25
    PR_UNASSIGNED             = 26
    PR_REVIEW_REQUESTED       = 27
    PR_REVIEW_REQUEST_REMOVED = 28
    PR_LABELED                = 29
    PR_UNLABELED              = 30
    PR_SYNCHRONIZE            = 31
    PR_READY_FOR_REVIEW       = 32
    PR_CONVERTED_TO_DRAFT     = 33
    PR_LOCKED                 = 34
    PR_UNLOCKED               = 35
    PR_AUTO_MERGE_ENABLED     = 36
    PR_AUTO_MERGE_DISABLED    = 37
    PR_MILESTONED             = 38
    PR_DEMILESTONED           = 39
    PR_REVIEW_SUBMITTED       = 40
    PR_REVIEW_EDITED          = 41
    PR_REVIEW_DISMISSED       = 42
    PR_REVIEW_COMMENT_CREATED = 43
    PR_REVIEW_COMMENT_EDITED  = 44
    PR_REVIEW_COMMENT_DELETED = 45

### Enum of event type groups
class EventTypeGroup(Enum):
    COMMIT_COMMENT = [
        EventType.COMMIT_COMMENT
    ]
    ISSUE_COMMENT = [
        EventType.ISSUE_COMMENT_CREATED,
        EventType.ISSUE_COMMENT_EDITED,
        EventType.ISSUE_COMMENT_DELETED
    ]
    ISSUE = [
        EventType.ISSUE_OPENED,
        EventType.ISSUE_EDITED,
        EventType.ISSUE_DELETED,
        EventType.ISSUE_PINNED,
        EventType.ISSUE_UNPINNED,
        EventType.ISSUE_CLOSED,
        EventType.ISSUE_REOPENED,
        EventType.ISSUE_ASSIGNED,
        EventType.ISSUE_UNASSIGNED,
        EventType.ISSUE_LABELED,
        EventType.ISSUE_UNLABELED,
        EventType.ISSUE_LOCKED,
        EventType.ISSUE_UNLOCKED,
        EventType.ISSUE_TRANSFERRED,
        EventType.ISSUE_MILESTONED,
        EventType.ISSUE_DEMILESTONED,
    ]
    PULL_REQUEST = [
        EventType.PR_OPENED,
        EventType.PR_CLOSED,
        EventType.PR_REOPENED,
        EventType.PR_EDITED,
        EventType.PR_ASSIGNED,
        EventType.PR_UNASSIGNED,
        EventType.PR_REVIEW_REQUESTED,
        EventType.PR_REVIEW_REQUEST_REMOVED,
        EventType.PR_LABELED,
        EventType.PR_UNLABELED,
        EventType.PR_SYNCHRONIZE,
        EventType.PR_READY_FOR_REVIEW,
        EventType.PR_CONVERTED_TO_DRAFT,
        EventType.PR_LOCKED,
        EventType.PR_UNLOCKED,
        EventType.PR_AUTO_MERGE_ENABLED,
        EventType.PR_AUTO_MERGE_DISABLED,
        EventType.PR_MILESTONED,
        EventType.PR_DEMILESTONED
    ]
    PULL_REQUEST_REVIEW = [
        EventType.PR_REVIEW_SUBMITTED,
        EventType.PR_REVIEW_EDITED,
        EventType.PR_REVIEW_DISMISSED
    ]
    PULL_REQUEST_REVIEW_COMMENT = [
        EventType.PR_REVIEW_COMMENT_CREATED,
        EventType.PR_REVIEW_COMMENT_EDITED,
        EventType.PR_REVIEW_COMMENT_DELETED
    ]

### Event types whitelists
staff_event_filter = [
    EventType.ISSUE_OPENED,
    EventType.ISSUE_DELETED,
    EventType.ISSUE_CLOSED,
    EventType.ISSUE_REOPENED,
    EventType.PR_OPENED,
    EventType.PR_CLOSED,
    EventType.PR_REOPENED,
    EventType.PR_READY_FOR_REVIEW,
    EventType.PR_REVIEW_SUBMITTED
]
external_event_filter = [
    EventType.COMMIT_COMMENT,
    EventType.ISSUE_COMMENT_CREATED,
    EventType.ISSUE_OPENED,
    EventType.ISSUE_DELETED,
    EventType.ISSUE_CLOSED,
    EventType.ISSUE_REOPENED,
    EventType.PR_OPENED,
    EventType.PR_CLOSED,
    EventType.PR_REOPENED,
    EventType.PR_READY_FOR_REVIEW,
    EventType.PR_REVIEW_SUBMITTED,
    EventType.PR_REVIEW_COMMENT_CREATED
]

### User blacklist
user_filter = [
    'github-actions[bot]'
]

### Repo blacklist
repo_filter = [
    'berty/bugs'
]

### Setup global logger
logger = logging.getLogger('webhook')
logger.setLevel(logging.INFO)
log_handler = RotatingFileHandler(log_path, maxBytes=max_logfile_bytes, backupCount=max_logfile_archives)
log_handler.setFormatter(logging.Formatter('%(asctime)-25s %(levelname)-10s %(message)s'))
logger.addHandler(log_handler)

def get_event_type(event):
    if 'issue' in event:
        if 'comment' in event:
            if event['action'] == 'created':
                return EventType.ISSUE_COMMENT_CREATED
            if event['action'] == 'edited':
                return EventType.ISSUE_COMMENT_EDITED
            if event['action'] == 'deleted':
                return EventType.ISSUE_COMMENT_DELETED
        else:
            if event['action'] == 'opened':
                return EventType.ISSUE_OPENED
            if event['action'] == 'edited':
                return EventType.ISSUE_EDITED
            if event['action'] == 'deleted':
                return EventType.ISSUE_DELETED
            if event['action'] == 'pinned':
                return EventType.ISSUE_PINNED
            if event['action'] == 'unpinned':
                return EventType.ISSUE_UNPINNED
            if event['action'] == 'closed':
                return EventType.ISSUE_CLOSED
            if event['action'] == 'reopened':
                return EventType.ISSUE_REOPENED
            if event['action'] == 'assigned':
                return EventType.ISSUE_ASSIGNED
            if event['action'] == 'unassigned':
                return EventType.ISSUE_UNASSIGNED
            if event['action'] == 'labeled':
                return EventType.ISSUE_LABELED
            if event['action'] == 'unlabeled':
                return EventType.ISSUE_UNLABELED
            if event['action'] == 'locked':
                return EventType.ISSUE_LOCKED
            if event['action'] == 'unlocked':
                return EventType.ISSUE_UNLOCKED
            if event['action'] == 'transferred':
                return EventType.ISSUE_TRANSFERRED
            if event['action'] == 'milestoned':
                return EventType.ISSUE_MILESTONED
            if event['action'] == 'demilestoned':
                return EventType.ISSUE_DEMILESTONED
    elif 'pull_request' in event:
        if 'comment' in event:
            if event['action'] == 'created':
                return EventType.PR_REVIEW_COMMENT_CREATED
            if event['action'] == 'edited':
                return EventType.PR_REVIEW_COMMENT_EDITED
            if event['action'] == 'deleted':
                return EventType.PR_REVIEW_COMMENT_DELETED
        elif 'number' in event:
            if event['action'] == 'opened':
                return EventType.PR_OPENED
            if event['action'] == 'edited':
                return EventType.PR_EDITED
            if event['action'] == 'closed':
                return EventType.PR_CLOSED
            if event['action'] == 'assigned':
                return EventType.PR_ASSIGNED
            if event['action'] == 'unassigned':
                return EventType.PR_UNASSIGNED
            if event['action'] == 'review_requested':
                return EventType.PR_REVIEW_REQUESTED
            if event['action'] == 'review_request_removed':
                return EventType.PR_REVIEW_REQUEST_REMOVED
            if event['action'] == 'ready_for_review':
                return EventType.PR_READY_FOR_REVIEW
            if event['action'] == 'converted_to_draft':
                return EventType.PR_CONVERTED_TO_DRAFT
            if event['action'] == 'labeled':
                return EventType.PR_LABELED
            if event['action'] == 'unlabeled':
                return EventType.PR_UNLABELED
            if event['action'] == 'synchronize':
                return EventType.PR_SYNCHRONIZE
            if event['action'] == 'auto_merge_enabled':
                return EventType.PR_AUTO_MERGE_ENABLED
            if event['action'] == 'auto_merge_disabled':
                return EventType.PR_AUTO_MERGE_DISABLED
            if event['action'] == 'locked':
                return EventType.PR_LOCKED
            if event['action'] == 'unlocked':
                return EventType.PR_UNLOCKED
            if event['action'] == 'reopened':
                return EventType.PR_REOPENED
        elif 'review' in event:
            if event['action'] == 'submitted':
                return EventType.PR_REVIEW_SUBMITTED
            if event['action'] == 'edited':
                return EventType.PR_REVIEW_EDITED
            if event['action'] == 'dismissed':
                return EventType.PR_REVIEW_DISMISSED
    elif 'comment' in event and 'commit_id' in event['comment']:
        if event['action'] == 'created':
            return EventType.COMMIT_COMMENT

    logger.warning('UNKNOWN event received: %s', json.dumps(event))

    return EventType.UNKNOWN

### Convert common actions to color code
def action_to_color(action):
    if action in ['closed', 'deleted', 'dismissed']:
        return '202225'
    if action == 'edited':
        return '373B40'
    return '2F3136'

### Convert event to embed message
def parse_event(event_type, event):
    embed = DiscordEmbed()

    ### Set author (common)
    embed.set_author(
        name     = event['sender']['login'],
        url      = event['sender']['html_url'],
        icon_url = event['sender']['avatar_url']
    )

    ### Set embed color (common)
    embed.set_color(action_to_color(event['action']))

    ### Parse event group specific attributes
    if event_type in EventTypeGroup.COMMIT_COMMENT.value:
        title = '[{repo}] Commit comment {action}: {commit_id}'.format(
            repo      = event['repository']['full_name'],
            action    = event['action'],
            commit_id = event['comment']['commit_id']
        )
        embed.set_title(title)
        embed.set_url(event['comment']['html_url'])
        embed.set_description(event['comment']['body'])
        embed.set_color('EAF0F3')

    elif event_type in EventTypeGroup.ISSUE_COMMENT.value:
        title = '[{repo}] Issue comment {action}: #{number} {title}'.format(
            repo   = event['repository']['full_name'],
            action = event['action'],
            number = event['issue']['number'],
            title  = event['issue']['title']
        )
        embed.set_title(title)
        embed.set_url(event['comment']['html_url'])
        if event['action'] in ['created', 'edited']:
            embed.set_description(event['comment']['body'])
        if event['action'] == 'created':
            embed.set_color('DAD100')

    elif event_type in EventTypeGroup.ISSUE.value:
        title = '[{repo}] Issue {action}: #{number} {title}'.format(
            repo   = event['repository']['full_name'],
            action = event['action'],
            number = event['issue']['number'],
            title  = event['issue']['title']
        )
        embed.set_title(title)
        embed.set_url(event['issue']['html_url'])
        if event['action'] in ['opened', 'edited']:
            embed.set_description(event['issue']['body'])
        if event['action'] in ['opened', 'reopened']:
            embed.set_color('EB6420')

    elif event_type in EventTypeGroup.PULL_REQUEST.value:
        title = '[{repo}] Pull request {action}: #{number} {title}'.format(
            repo   = event['repository']['full_name'],
            action = event['action'],
            number = event['pull_request']['number'],
            title  = event['pull_request']['title']
        )
        embed.set_title(title)
        embed.set_url(event['pull_request']['html_url'])
        if event['action'] in ['opened', 'edited']:
            embed.set_description(event['pull_request']['body'])
        if event['action'] in ['opened', 'reopened']:
            embed.set_color('009801')

    elif event_type in EventTypeGroup.PULL_REQUEST_REVIEW.value:
        title = '[{repo}] Pull request review {action}: #{number} {title}'.format(
            repo   = event['repository']['full_name'],
            action = event['action'],
            number = event['pull_request']['number'],
            title  = event['pull_request']['title']
        )
        embed.set_title(title)
        embed.set_url(event['review']['html_url'])
        if event['action'] in ['submitted', 'edited']:
            embed.set_description(event['review']['body'])
        if event['action'] == 'submitted':
            embed.set_color('03B2F8')

    elif event_type in EventTypeGroup.PULL_REQUEST_REVIEW_COMMENT.value:
        title = '[{repo}] Pull request review comment {action}: #{number} {title}'.format(
            repo   = event['repository']['full_name'],
            action = event['action'],
            number = event['pull_request']['number'],
            title  = event['pull_request']['title']
        )
        embed.set_title(title)
        embed.set_url(event['comment']['html_url'])
        desc = '''
        **{path}**
        ```diff
        {diff}
        ```
        {comment}
        '''.format(
            path    = event['comment']['path'],
            diff    = event['comment']['diff_hunk'],
            comment = event['comment']['body']
        )
        if event['action'] in ['created', 'edited']:
            embed.set_description(desc)
        if event['action'] == 'created':
            embed.set_color('6ED5FF')

    return embed

## Check via Github API if event author is a staff of the event repo
def is_author_staff(event):
    url = 'https://api.github.com/repos/%s/collaborators/%s/permission' % (event['repository']['full_name'], event['sender']['login'])
    headers = {'Authorization': 'token %s' % github_api_token}
    response = requests.get(url, headers=headers)

    if response.status_code not in [200, 204]:
        raise Exception(
            'author permission request failed: (code: %d), (text: %s), (repo: %s, user: %s)',
            response.status_code,
            response.text,
            event['repository']['full_name'],
            event['sender']['login']
        )

    try:
        permission = json.loads(response.text)['permission']
        if permission in ['write', 'admin']:
            return True
        return False
    except:
        raise Exception(
            'author permission request response malformed: (text: %s), (repo: %s, user: %s)',
            response.text,
            event['repository']['full_name'],
            event['sender']['login']
        )


### Send formated embed message to specified webhook url
def send_to_discord(webhook_url, embed):
    webhook = DiscordWebhook(url=webhook_url)
    webhook.add_embed(embed)
    responses = webhook.execute()

    if type(responses) is not list: responses = [responses]

    for response in responses:
        if response.status_code not in [200, 204]:
            logger.error(
                'executing webhook failed: (code: %d), (text: %s), (author: %s, title: %s, description: %s)',
                response.status_code,
                response.text,
                embed.author['name'],
                embed.title,
                embed.description
            )
            return

    logger.info('event sent to discord successfully: %s', embed.title)

def handle_event(event):
    ### Determine event type
    event_type = get_event_type(event)

    ### Filter event accordingly to user and repo blacklists
    if event['sender']['login'] in user_filter:
        logger.info('user (%s) is in blacklist: event [%s] skipped', event['sender']['login'], event_type.name)
        return
    elif event['repository']['full_name'] in repo_filter:
        logger.info('repo (%s) is in blacklist: event [%s] skipped', event['repository']['full_name'], event_type.name)
        return

    ### Check if event author is a staff user
    is_staff = is_author_staff(event)

    ### Filter event accordingly to user/event type whitelist
    if is_staff and event_type in staff_event_filter:
        embed = parse_event(event_type, event)
        send_to_discord(github_staff, embed)
    elif not is_staff and event_type in external_event_filter:
        embed = parse_event(event_type, event)
        send_to_discord(github_external, embed)
    else:
        logger.info('event [%s] skipped for %s user', event_type.name, 'staff' if is_staff else 'external')

if __name__ == "__main__":
    ### Get the Github webhook payload from sys args
    with open(sys.argv[1], 'r') as payload:
        event = json.loads(payload.read())

    try:
        handle_event(event)
    except Exception as detail:
        logger.error('can not handle event: %s', detail)
