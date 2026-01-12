# Tests Directory

## Overview

This directory contains comprehensive test suites for the Blackjack client-server application. The tests verify protocol compliance, game logic, message handling, and integration between components.

## Files

### `test_blackjack.py`
**Purpose**: Comprehensive unit and integration tests

**Functionality**:
- Tests card encoding/decoding
- Tests deck functionality
- Tests game logic (dealer rules, winner determination)
- Tests message creation and parsing
- Tests protocol compliance
- Tests edge cases (long names, invalid messages, etc.)

**Coverage**:
- Card class and encoding
- Deck shuffling and drawing
- Blackjack game logic
- Message format validation
- Error handling

**Usage**:
```bash
python3 tests/test_blackjack.py
# or
python3 -m pytest tests/test_blackjack.py -v
```

### `test_integration.py`
**Purpose**: End-to-end integration tests

**Functionality**:
- Tests full client-server interaction
- Tests multiple rounds
- Tests concurrent clients
- Tests error scenarios
- Tests statistics tracking

**Usage**:
```bash
python3 tests/test_integration.py
```

### `test_web_integration.py`
**Purpose**: Web interface integration tests

**Functionality**:
- Tests web bridge functionality
- Tests HTTP API endpoints
- Tests SSE event streaming
- Tests session management
- Tests web interface communication

**Usage**:
```bash
python3 tests/test_web_integration.py
```

### `test_web_interface.py`
**Purpose**: Web interface component tests

**Functionality**:
- Tests web bridge handler
- Tests game session management
- Tests event queue
- Tests state management

**Usage**:
```bash
python3 tests/test_web_interface.py
```

### `test_web_manual.py`
**Purpose**: Manual testing guide and helpers

**Functionality**:
- Provides manual testing procedures
- Helper functions for manual testing
- Test scenarios documentation

**Usage**: Reference for manual testing procedures

## Instructions

### Running All Tests

```bash
# From project root
python3 -m pytest tests/ -v

# Or run individual test files
python3 tests/test_blackjack.py
python3 tests/test_integration.py
python3 tests/test_web_integration.py
```

### Test Requirements

- Python 3.7+
- Standard library only (no external dependencies)
- Tests use `unittest` framework (built-in)

### Test Categories

1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test components working together
3. **Protocol Tests**: Verify protocol compliance
4. **Edge Case Tests**: Test boundary conditions and error handling
5. **Web Tests**: Test web interface functionality

### Expected Results

All tests should pass:
- ✅ Card encoding/decoding
- ✅ Message format validation
- ✅ Game logic correctness
- ✅ Protocol compliance
- ✅ Error handling
- ✅ Integration scenarios

### Troubleshooting

- **Tests fail**: Check that no other server/client is running on the same ports
- **Port conflicts**: Tests use random ports, but may conflict if many tests run simultaneously
- **Import errors**: Make sure you're running from project root or tests directory

## Test Coverage

The test suite covers:
- ✅ All message types (offer, request, payload)
- ✅ Card encoding and decoding
- ✅ Game logic (dealer rules, winner determination)
- ✅ Error handling (invalid messages, timeouts)
- ✅ Edge cases (long names, empty messages)
- ✅ Integration scenarios (full game rounds)
- ✅ Web interface functionality

