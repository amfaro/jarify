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
    timeout_ms = 2000,
    lsp_fallback = false,
  },
})
```

## nvim-lint — inline diagnostics

```lua
local lint = require("lint")

lint.linters.jarify = {
  cmd = "jarify",
  stdin = true,
  args = { "lint", "--format", "json", "--stdin-filename", function() return vim.fn.expand("%") end, "-" },
  stream = "stdout",
  ignore_exitcode = true,
  parser = function(output)
    local diagnostics = {}
    for _, v in ipairs(output ~= "" and vim.json.decode(output) or {}) do
      table.insert(diagnostics, {
        lnum     = (v.line or 1) - 1,
        col      = (v.column or 1) - 1,
        message  = ("[%s] %s"):format(v.rule, v.message),
        severity = v.severity == "error" and vim.diagnostic.severity.ERROR or vim.diagnostic.severity.WARN,
        source   = "jarify",
      })
    end
    return diagnostics
  end,
}

lint.linters_by_ft = { sql = { "jarify" } }

vim.api.nvim_create_autocmd({ "BufWritePost", "BufReadPost", "InsertLeave" }, {
  callback = function() lint.try_lint() end,
})
```

