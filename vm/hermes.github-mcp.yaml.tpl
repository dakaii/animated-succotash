
mcp_servers:
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_PAT}"
    tools:
      include:
        - list_issues
        - create_issue
        - update_issue
        - search_code
        - get_file_contents
        - create_or_update_file
        - create_pull_request
        - list_pull_requests
        - get_pull_request
        - create_pull_request_review
      prompts: false
      resources: false
