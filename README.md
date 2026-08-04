### Memo Management System

A memo management system is a digital solution that helps users create, organize, store, and manage memos or notes efficiently. It streamlines communication and information tracking by allowing easy access, editing, categorization, and sharing of important memos within an app or organization.

### Documentation

- [Training Manual](./TRAINING_MANUAL.md)

### Current Feature Set

- formal memo creation with category, priority, confidentiality, and origin details
- approval and rejection workflow with routing history
- recipient circulation with optional acknowledgement tracking
- follow-up action points with assignees, due dates, and status tracking
- related document linking for records such as `Material Request` and `Purchase Order`
- governance reporting and an `Official Memo` print format

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app memo_management_system
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/memo_management_system
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
