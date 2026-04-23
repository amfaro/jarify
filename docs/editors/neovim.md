# Neovim

Formatting via [`conform.nvim`](https://github.com/stevearc/conform.nvim) and diagnostics via [`nvim-lint`](https://github.com/mfussenegger/nvim-lint).

## Prerequisites

- `jarify` on your `PATH` — see [Editor Clients](README.md#prerequisites)
- `conform.nvim` and `nvim-lint` installed

## conform.nvim — format on save

```lua
require("conform").setup({
  formatters_by_ft = {
    sql = { "jarify" },
  },
  formatters = {
    jarify = {
      command = "jarify",
      args = { "fmt", "--stdin-filename", "$FILENAME", "-" },
      stdin = true,
    },
  },
  format_on_save = {
    timeout_ms = 500,
    lsp_format = "fallback",
  },
})
```

## nvim-lint — inline diagnostics

```lua
local lint = require("lint")

local severity_map = {
  error = vim.diagnostic.severity.ERROR,
  warn  = vim.diagnostic.severity.WARN,
}

lint.linters.jarify = {
  cmd = "jarify",
  stdin = true,
  args = {
    "lint", "--format", "json",
    "--stdin-filename", function() return vim.api.nvim_buf_get_name(0) end,
    "-",
  },
  ignore_exitcode = true,
  parser = function(output, bufnr)
    if output == nil or vim.trim(output) == "" then return {} end

    local ok, decoded = pcall(vim.json.decode, output)
    if not ok then return {} end

    local filename = vim.fs.normalize(vim.api.nvim_buf_get_name(bufnr))
    local diagnostics = {}

    for _, item in ipairs(decoded or {}) do
      local item_file = item.filename and vim.fs.normalize(item.filename) or filename
      if item_file == filename then
        local lnum = math.max((item.line or 1) - 1, 0)
        local col  = math.max((item.column or 1) - 1, 0)
        table.insert(diagnostics, {
          lnum     = lnum,
          col      = col,
          end_lnum = lnum,
          end_col  = col,
          message  = string.format("[%s] %s", item.rule or "jarify", item.message),
          code     = item.rule,
          source   = "jarify",
          severity = severity_map[item.severity] or vim.diagnostic.severity.WARN,
        })
      end
    end

    return diagnostics
  end,
}

lint.linters_by_ft = { sql = { "jarify" } }

vim.api.nvim_create_autocmd({ "BufReadPost", "BufEnter", "InsertLeave", "BufWritePost" }, {
  callback = function() vim.schedule(lint.try_lint) end,
})
```
