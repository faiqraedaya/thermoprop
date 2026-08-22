# ThermoProp

Thermophysical properties calculator for pure fluids and mixtures.

## Features

- Calculate 15+ thermodynamic and transport properties for pure fluids at any state point
- Mixture properties using ideal-gas or humid-air mixing rules with user-defined compositions
- Saturation properties (liquid/vapor) at a specified temperature or pressure
- Process path simulation: isobaric, isochoric, isothermal, isenthalpic, isentropic, and polytropic
- Interactive thermodynamic diagrams: T-S, P-H, P-V, H-S, saturation curves, and phase envelopes

## Installation

```bash
git clone https://github.com/faiqraedaya/ThermoProp
cd ThermoProp
uv sync
```

## Usage

```bash
uv run thermoprop
# or
uv run python main.py
```

## Tests

Reference-state and process-path invariant tests (NIST/CoolProp cross-checks):

```bash
uv run pytest
```

## License

[MIT](LICENSE)
