# tree

- tree of dir, files, and stubs
- a stub is a single spec line, e.g. the signature of a function
- every surface construct is present
- a tag is a bracketed marker after a stub, e.g. [{idx}]

```text
{dir}
├── {file}
│   ├ {stub} {tags}
│   └ {stub}
└── {dir}
    └── {file}
        ├ {stub}
        …
```

## example

```text
{name}
├── shelf.rs
│   ├ add_book(ShelfId, BookId) → SlotId
│   ├ book_ids(ShelfId) → Vec<BookId>
│   └ iter_slots() → impl Iterator<Item = SlotId>
├── loan.rs
│   ├ borrow(BookId, MemberId) → Result<LoanId, BookOnLoanError>
│   └ find_loan(BookId) → Option<LoanId>
└── store/
    └── sqlite.rs
        ├ open(&str) → Result<StoreSqlite, ConnectError>
        └ prune_returned() → u32
```
