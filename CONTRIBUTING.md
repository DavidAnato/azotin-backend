# Contributing Guide

Thank you for considering contributing to this project! This document outlines the rules and best practices to follow for effective contributions.

## Project Setup

### Prerequisites

- **Python 3.10**

### Installation

1. Clone the repository:

   ```bash
   git clone git@github.com:LATOURE-LABS/jobhub_api.git
   cd jobhub_api

  ```
2. Set up environment variables:

   ```bash
   cp .env.example .env
   ```

3. Set up the virtual environment and install dependencies:

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

   ```

4. Configure the environment variables for your database and JWT settings.
5. Run the database migrations:

   ```bash
   python manage.py migrate
   ```

6. Start the Django server:

   ```bash
    python manage.py runserver
   ```

## Code Formatting and Linting

To maintain a consistent and clean codebase, we enforce strict guidelines for code formatting and linting using the following tools:  

- **[Black](https://black.readthedocs.io/)**: An opinionated code formatter to ensure consistent style.  
- **[isort](https://pycqa.github.io/isort/)**: A tool to sort and organize imports.  
- **[Flake8](https://flake8.pycqa.org/)**: A linter to detect style violations, unused imports, and potential bugs.  

  ### Usage

   Before committing, run:

   ```bash
   isort .
   flake8 .
   ```

## Commit Conventions

We follow the Conventional Commits format to ensure a readable and structured Git history. Commit messages must follow this format:

```scss
type(scope): message;
```

### Accepted Types

- **feat:** For new features.
- **fix:** For bug fixes.
- **docs:** For changes in documentation.
- **style:** For code style changes (formatting, etc.) that don’t affect functionality.
- **refactor:** For code changes that neither fix a bug nor add a feature.
- **test:** For adding or modifying tests.
- **chore:** For minor tasks such as dependency updates.

#### Examples

```scss
feat(auth): add JWT-based authentication
fix(profile): fix email validation issue
```

## Branching Strategy

We use Git Flow as our branching strategy. Below are the key branches and their usage:

- **main:** Production branch, always stable.
- **preprod:** Pre-production branch, receives hotfixes.
- **develop:** Development branch, receives new features.
- **feature/feature-name:** Feature branches for developing new features.
- **hotfix/hotfix-name:** Hotfix branches for critical bug fixes in production.
- **release/x.x.x:** Release branches for preparing new versions.

  ### Rules

- **No direct commits** to `main` or `develop`.
- **Pull Requests** (PR) are required to merge into develop or main.
- **Code review** is mandatory for every PR before merging.
