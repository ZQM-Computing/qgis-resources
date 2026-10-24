# Contributing to ZQM Computing

Thank you for your interest in contributing to ZQM Computing — geospatial patterns and tools.

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## Code Standards

- Follow existing code style
- Add tests for new features; prefer small synthetic fixtures with known expected results
- Follow [the geospatial workflow contracts](docs/WORKFLOW_CONTRACTS.md) for CRS/units, input validation, output verification, overwrite behavior, cancellation, and cleanup
- Update the README or relevant resource guide and the [product roadmap](docs/PRODUCT_ROADMAP.md) when scope or status changes
- Keep commits atomic and descriptive
- All repos are MIT-licensed unless otherwise noted

## Definition of done

A new or materially changed resource should identify its use case, supported environment, inputs and outputs, CRS/measurement assumptions, failure behavior, and limitations. Add an executable example and tests that assert meaningful results where feasible. State whether it is implemented, static-checked, runtime-tested, or validated for use; do not claim runtime validation from syntax checks or source-text assertions alone. Never silently overwrite user data or guess a missing CRS.

## Reporting Issues

- Use GitHub Issues for bug reports
- Include steps to reproduce
- Specify your environment (OS, version, etc)
- For security vulnerabilities, see [SECURITY.md](SECURITY.md)

## Questions?

Open an issue or discussion in the repository.

---

*Part of the [ZQM Computing](https://github.com/ZQM-Computing) ecosystem — geospatial patterns and tools.*
