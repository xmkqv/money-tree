# telegram-bot

- verified: core.telegram.org on 2026-08-11
- window: bot api 9.4 (2026-02-09) through 10.2 (2026-07-14)
- community claims are marked; everything else is primary

[changelog][changelog]
    bot api ships roughly monthly: 9.4 on 2026-02-09, 9.5 on 2026-03-01, 9.6 on 2026-04-03, 10.0 on 2026-05-08, 10.1 on 2026-06-11, 10.2 on 2026-07-14
    9.5 expanded message streaming to all bots
    9.6 added getManagedBotToken and replaceManagedBotToken
    10.0 introduced guest mode, letting a bot receive and reply in chats it does not belong to
    10.0 added deleteMessageReaction and deleteAllMessageReactions
    10.2 introduced ephemeral messages visible only to one named user and the bot
    10.2 introduced communities linking supergroups, channels and bots

[buttons][buttons]
    pressing an inline keyboard button sends no message to the chat
    telegram advises editing the keyboard in place on toggle or navigation rather than sending a new message
    a menu button sits beside the message field in every bot chat and holds commands or a web app
    command scopes show different commands to different users, and updates never say which scope a command came from
    a deep link start parameter allows a-z, digits, underscore and dash, up to 64 characters
    [buttons style][changelog]
        9.4 added style to InlineKeyboardButton and KeyboardButton, letting a bot set button color
        9.4 added icon_custom_emoji_id to both button classes
        a custom emoji on a button requires the bot owner to hold telegram premium
        the style values primary, success and danger are community-reported, not stated on core.telegram.org
    [buttons limits][buttons.limits]
        callback_data is utf-8 and 1 to 64 bytes
        answerCallbackQuery text is 0 to 200 characters
        show_alert true renders a dismissible modal instead of a toast
        cache_time bounds how long a client may cache a callback query result

[width][width]
    telegram documents no parameter for message bubble width, button width, or card width
    resize_keyboard exists only on ReplyKeyboardMarkup and has no inline equivalent
    the mtproto button documentation states no row limit, layout, or width constraint
    inline button width is client-determined and cannot be set by the bot
    the only lever a bot holds over inline layout is buttons per row
    a card is as wide as its widest text line or widest button label
    braille blank u+2800 is the community filler because ordinary spaces collapse
    no evidence was found that invisible padding trips anti-spam on a bot's own outgoing messages, in either direction

[checklists][changelog]
    sendChecklist sends a checklist on behalf of a business account, so a plain bot cannot post one
    editMessageChecklist likewise acts on behalf of a business account
    no version from 9.2 through 10.2 lifts the business-account restriction
    checklists shipped in 9.1 on 2025-07-03
    a task status change arrives as the checklist_tasks_done service message on Message
    an added task arrives as the checklist_tasks_added service message on Message
    InputChecklist holds a title of 1 to 255 characters and 1 to 30 tasks
    others_can_add_tasks and others_can_mark_tasks_as_done govern who may edit the list

[rich messages][changelog]
    10.1 added rich messages for highly structured text and streamed replies
    sendRichMessage takes business_connection_id as optional, so a plain bot may send one
    sendRichMessageDraft streams a partial rich message
    10.2 added InputRichMessageMedia and the media field on InputRichMessage
    exactly one of html, markdown, or blocks may be set on InputRichMessage
    a block carries a type discriminator: paragraph, heading, divider, list, details, quotation, table, preformatted, and media kinds
    a heading carries a size of 1 to 6
    a details block carries a summary, nested blocks, and an is_open flag
    a list item carries nested blocks plus optional has_checkbox and is_checked
    rich text is a plain string, an array of rich text, or a formatting object such as bold or code
    editing a streamed message with editMessageText strips its rich formatting, because the edit carries no parse mode — community

[mini apps][mini-apps]
    from 2026-07-20 a site opened from a link inside a mini app cannot call mini app methods
    the origin protection applied automatically to every mini app and is opted out through botfather
    opting out makes the bot responsible for the trustworthiness of every link in the mini app
    the window added only iconCustomEmojiId on BottomButton in 9.5 and requestChat on WebApp in 9.6
    full screen, orientation locking and home screen shortcuts predate the window, shipping in 8.0 on 2024-11-17
    device storage is capped at 5 mb per user and secure storage at 10 items per user

[stars][stars]
    digital goods and services sell exclusively in telegram stars under the currency tag xtr
    a bot taking star payments must support both a terms command and a paysupport command
    the developer bears full responsibility for disputes and chargebacks
    refunds are issued with refundStarPayment
    a star amount varies per user because of vat and other fees outside telegram's control
    no star pricing or payout change is documented inside the window
    10.2 added BotSubscriptionUpdated and the subscription field on Update

[flood][flood]
    flood limits sit near 30 messages per second overall and 20 per minute in one group — community
    retrying sends while ignoring api errors risks a temporary ban — community

[bot to bot][bot-to-bot]
    bot to bot communication was permitted on 2026-04-05 in specific contexts
    it works in groups and in business mode and is enabled through botfather
    no new restriction on a personal single-user bot appeared inside the window

## refs

[changelog]: https://core.telegram.org/bots/api-changelog
[buttons]: https://core.telegram.org/bots/features
[buttons.limits]: https://core.telegram.org/bots/api
[width]: https://core.telegram.org/api/bots/buttons
[mini-apps]: https://core.telegram.org/bots/webapps
[stars]: https://core.telegram.org/bots/payments-stars
[flood]: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Avoiding-flood-limits
[bot-to-bot]: https://t.me/s/BotNews
