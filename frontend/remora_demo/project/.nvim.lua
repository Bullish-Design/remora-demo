-- remora_demo/project/.nvim.lua
-- Auto-loaded by Neovim when opening files in this directory
-- (requires `set exrc` in init.lua)

vim.lsp.start({
    name = "remora-demo",
    cmd = { "python", "-m", "remora_demo" },
    root_dir = vim.fn.getcwd(),
    settings = {},
})

-- Set updatetime for responsive cursor tracking
vim.opt.updatetime = 300
