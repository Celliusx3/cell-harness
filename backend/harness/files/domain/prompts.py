"""What a bot is told of a workspace's memory on every step."""

WORKSPACE_MEMORY = "Your memory, {path}:"
WORKSPACE_NO_MEMORY = "You have no memory yet: {path} does not exist."
GROUP_MEMORY = "This group's memory, {path}:"
GROUP_NO_MEMORY = "This group has no memory yet: {path} does not exist."
WORKSPACE_MEMORY_CUT = (
    "{path} has {total} lines and only the first {shown} are shown. Keep it short: "
    "move details into other files and leave one line pointing to each."
)
WORKSPACE_MEMORY_CHARS_CUT = (
    "{path} has {total} characters and only the first {shown} are shown. Keep it short: "
    "move details into other files and leave one line pointing to each."
)
