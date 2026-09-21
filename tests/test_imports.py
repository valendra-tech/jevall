def test_public_package_imports_without_model_runtime_dependencies():
    import jevall
    from jevall.__main__ import main

    assert jevall.__version__ == "0.1.0"
    assert callable(main)
