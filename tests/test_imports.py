def test_public_package_imports_without_model_runtime_dependencies():
    import jev_gate
    from jev_gate.__main__ import main

    assert jev_gate.__version__ == "0.1.0"
    assert callable(main)
