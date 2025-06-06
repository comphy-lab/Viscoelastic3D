---
trigger: model_decision
description: Apply when working on documentation or website-related tasks using the GitHub scripts.
globs: 
---
---
title: Basilisk Documentation Generation
description: Guidelines for documentation and website generation
globs: [".github/**/*"]
---

## Documentation Generation

- Read `.github/Website-generator-readme.md` for the website generation process.
- Do not auto-deploy the website; generating HTML is permitted using `.github/scripts/build.sh`.
- Avoid editing HTML files directly; they are generated using `.github/scripts/build.sh`, which utilizes `.github/scripts/generate_docs.py`.
- The website is deployed at `https://comphy-lab.org/repositoryName`; refer to the `CNAME` file for configuration. Update if not done already. 

## Purpose

This rule provides guidance for maintaining and generating documentation for code repositories in the CoMPhy Lab, ensuring consistency and proper workflow for website generation.

## Process Details

The documentation generation process utilizes Python scripts to convert source code files into HTML documentation. The process handles C/C++, Python, Shell, and Markdown files, generating a complete documentation website with navigation, search functionality, and code highlighting.

## Best Practices

- Always use the build script for generating documentation rather than manually editing HTML files
- Customize styling through CSS files in `.github/assets/css/`
- Modify functionality through JavaScript files in `.github/assets/js/`
- For template changes, edit `.github/assets/custom_template.html`
- Troubleshoot generation failures by checking error messages and verifying paths and dependencies