import os
import re
import platform

import mock
from mock import Mock

from conan.tools.google import BazelDeps
from conan import ConanFile
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.dependencies import ConanFileDependencies
from conans.model.build_info import CppInfo
from conans.model.recipe_ref import RecipeReference
from conans.model.requires import Requirement
from conans.test.utils.mocks import MockOptions
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


def test_bazeldeps_dependency_buildfiles():
    conanfile = ConanFile(Mock())
    package_folder = temp_folder()

    cpp_info = CppInfo()
    cpp_info.defines = ["DUMMY_DEFINE=\"string/value\""]
    cpp_info.system_libs = ["system_lib1"]
    cpp_info.libs = ["lib1"]
    cpp_info.libdirs = [os.path.join(package_folder, "lib")]

    conanfile_dep = ConanFile(Mock())
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("depname/1.0")

    save(os.path.join(cpp_info.libdirs[0], "liblib1.a"), "")
    conanfile_dep.folders.set_base_package(package_folder)

    cpp_info.libdirs = [str(os.path.join(package_folder, "lib"))]

    # FIXME: This will run infinite loop if conanfile.dependencies.host.topological_sort.
    #  Move to integration test
    with mock.patch('conan.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(RecipeReference.loads("depname/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})
        bazeldeps = BazelDeps(conanfile)

        for dependency in bazeldeps._conanfile.dependencies.host.values():
            dependency_content = bazeldeps._get_dependency_buildfile_content(dependency)
            assert 'cc_library(\n    name = "depname",' in dependency_content
            assert """defines = ["DUMMY_DEFINE=\\\\\\"string/value\\\\\\""]""" in dependency_content
            if platform.system() == "Windows":
                assert 'linkopts = ["/DEFAULTLIB:system_lib1"]' in dependency_content
            else:
                assert 'linkopts = ["-lsystem_lib1"],' in dependency_content
            assert """deps = [\n        # do not sort\n        ":lib1_precompiled",""" in dependency_content


def test_bazeldeps_get_lib_file_path_by_basename():
    conanfile = ConanFile(Mock())
    package_folder = temp_folder()

    cpp_info = CppInfo()
    cpp_info.defines = ["DUMMY_DEFINE=\"string/value\""]
    cpp_info.system_libs = ["system_lib1"]
    cpp_info.libs = ["liblib1.a"]
    cpp_info.libdirs = [os.path.join(package_folder, "lib")]

    conanfile_dep = ConanFile(Mock())
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("depname/1.0")

    save(os.path.join(package_folder, "lib", "liblib1.a"), "")
    conanfile_dep.folders.set_base_package(package_folder)

    cpp_info.libdirs = [str(os.path.join(package_folder, "lib"))]

    # FIXME: This will run infinite loop if conanfile.dependencies.host.topological_sort.
    #  Move to integration test
    with mock.patch('conan.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(RecipeReference.loads("depname/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})
        bazeldeps = BazelDeps(conanfile)

        for dependency in bazeldeps._conanfile.dependencies.host.values():
            dependency_content = bazeldeps._get_dependency_buildfile_content(dependency)
            assert 'cc_library(\n    name = "depname",' in dependency_content
            assert """defines = ["DUMMY_DEFINE=\\\\\\"string/value\\\\\\""]""" in dependency_content
            if platform.system() == "Windows":
                assert 'linkopts = ["/DEFAULTLIB:system_lib1"]' in dependency_content
            else:
                assert 'linkopts = ["-lsystem_lib1"],' in dependency_content
            assert 'deps = [\n        # do not sort\n        ":liblib1.a_precompiled",' in dependency_content


def test_bazeldeps_dependency_transitive():
    # Create main ConanFile
    conanfile = ConanFile(Mock())

    cpp_info = CppInfo()
    cpp_info.defines = ["DUMMY_DEFINE=\"string/value\""]
    cpp_info.system_libs = ["system_lib1"]
    cpp_info.libs = ["lib1"]

    # Create a ConanFile for a direct dependency
    conanfile_dep = ConanFile(Mock())
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("depname/1.0")
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")
    package_folder = temp_folder()
    save(os.path.join(package_folder, "lib", "liblib1.a"), "")
    conanfile_dep.folders.set_base_package(package_folder)

    cpp_info.libdirs = [str(os.path.join(package_folder, "lib"))]

    # Add dependency on the direct dependency
    req = Requirement(RecipeReference.loads("depname/1.0"))
    conanfile._conan_dependencies = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

    cpp_info_transitive = CppInfo()
    cpp_info_transitive.defines = ["DUMMY_DEFINE=\"string/value\""]
    cpp_info_transitive.system_libs = ["system_lib1"]
    cpp_info_transitive.libs = ["lib_t1"]

    # Create a ConanFile for a transitive dependency
    conanfile_dep_transitive = ConanFile(Mock())
    conanfile_dep_transitive.cpp_info = cpp_info_transitive
    conanfile_dep_transitive._conan_node = Mock()
    conanfile_dep_transitive._conan_node.ref = RecipeReference.loads("transitive_depname/1.0")
    conanfile_dep_transitive.folders.set_base_package("/path/to/folder_dep_t")

    # Add dependency from the direct dependency to the transitive dependency
    req = Requirement(RecipeReference.loads("transitive_depname/1.0"))
    conanfile_dep._conan_dependencies = ConanFileDependencies(
        {req: ConanFileInterface(conanfile_dep_transitive)})

    bazeldeps = BazelDeps(conanfile)

    for dependency in bazeldeps._conanfile.dependencies.host.values():
        dependency_content = bazeldeps._get_dependency_buildfile_content(dependency)
        assert 'cc_library(\n    name = "depname",' in dependency_content
        assert 'defines = ["DUMMY_DEFINE=\\\\\\"string/value\\\\\\""],' in dependency_content
        if platform.system() == "Windows":
            assert 'linkopts = ["/DEFAULTLIB:system_lib1"],' in dependency_content
        else:
            assert 'linkopts = ["-lsystem_lib1"],' in dependency_content

        # Ensure that transitive dependency is referenced by the 'deps' attribute of the direct
        # dependency
        assert re.search(r'deps =\s*\[\s*# do not sort\s*":lib1_precompiled",\s*"@transitive_depname"',
                         dependency_content)


def test_bazeldeps_interface_buildfiles():
    conanfile = ConanFile(Mock())

    cpp_info = CppInfo()

    conanfile_dep = ConanFile(Mock())
    conanfile_dep.cpp_info = cpp_info
    cpp_info.includedirs = ["include"]
    conanfile_dep._conan_node = Mock()
    conanfile_dep.folders.set_base_package(temp_folder())
    conanfile_dep._conan_node.ref = RecipeReference.loads("depname/2.0")

    # FIXME: This will run infinite loop if conanfile.dependencies.host.topological_sort.
    #  Move to integration test
    with mock.patch('conan.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(RecipeReference.loads("depname/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        bazeldeps = BazelDeps(conanfile)

        dependency = next(iter(bazeldeps._conanfile.dependencies.host.values()))
        content = bazeldeps._get_dependency_buildfile_content(dependency)
        dependency_content = re.sub(r"\s", "", content)
        assert(dependency_content == 'load("@rules_cc//cc:defs.bzl","cc_import","cc_library")cc_library(name="depname",hdrs=glob(["include/**"]),includes=["include"],visibility=["//visibility:public"],)')


def test_bazeldeps_shared_library_interface_buildfiles():
    conanfile = ConanFile(Mock())
    cpp_info = CppInfo()
    cpp_info.libs = ["lib1"]
    cpp_info.libdirs = ["lib"]
    cpp_info.bindirs = ["bin"]
    cpp_info.includedirs = ["include"]

    options = MockOptions({"shared": True})
    conanfile_dep = ConanFile(Mock())
    conanfile_dep.options = options
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("depname/1.0")
    conanfile_dep._conan_node.transitive_deps = {}

    package_folder = temp_folder()
    save(os.path.join(package_folder, "lib", "lib1.lib"), "")
    save(os.path.join(package_folder, "bin", "lib1.dll"), "")
    cpp_info.set_relative_base_folder(package_folder)
    conanfile_dep.folders.set_base_package(package_folder)

    req = Requirement(RecipeReference.loads("depname/1.0"))
    conanfile._conan_dependencies = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

    bazeldeps = BazelDeps(conanfile)

    dependency = next(iter(bazeldeps._conanfile.dependencies.host.values()))
    dependency_content = re.sub(r"\s",
                                "",
                                bazeldeps._get_dependency_buildfile_content(dependency))
    expected_content = """
load("@rules_cc//cc:defs.bzl","cc_import","cc_library")

cc_import(
    name = "lib1_precompiled",
    interface_library = "lib/lib1.lib",
    shared_library = "bin/lib1.dll",
)

cc_library(
    name = "depname",
    hdrs=glob(["include/**"]),
    includes=["include"],
    visibility=["//visibility:public"],
    deps = [
        # do not sort
        ":lib1_precompiled",
    ],
)
"""
    assert(dependency_content == re.sub(r"\s", "", expected_content))


def test_bazeldeps_main_buildfile():
    expected_content = [
        'def load_conan_dependencies():',
        'native.new_local_repository(',
        'name="depname",',
        'path="/path/to/folder_dep",',
        'build_file="conandeps/depname/BUILD",'
    ]

    conanfile = ConanFile(None)

    cpp_info = CppInfo(set_defaults=True)

    conanfile_dep = ConanFile(None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("depname/1.0")
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")

    # FIXME: This will run infinite loop if conanfile.dependencies.host.topological_sort.
    #  Move to integration test
    with mock.patch('conan.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(RecipeReference.loads("depname/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        bazeldeps = BazelDeps(conanfile)

        local_repositories = []
        for dependency in bazeldeps._conanfile.dependencies.host.values():
            content = bazeldeps._create_new_local_repository(dependency,
                                                             "conandeps/depname/BUILD")
            local_repositories.append(content)

        content = bazeldeps._get_main_buildfile_content(local_repositories)

        for line in expected_content:
            assert line in content


def test_bazeldeps_build_dependency_buildfiles():
    conanfile = ConanFile()

    conanfile_dep = ConanFile()
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("depname/1.0")
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")

    # FIXME: This will run infinite loop if conanfile.dependencies.host.topological_sort.
    #  Move to integration test
    with mock.patch('conan.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(RecipeReference.loads("depname/1.0"), build=True)
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        bazeldeps = BazelDeps(conanfile)

        for build_dependency in bazeldeps._conanfile.dependencies.direct_build.values():
            dependency_content = bazeldeps._get_build_dependency_buildfile_content(build_dependency)
            assert 'filegroup(\n    name = "depname_binaries",' in dependency_content
            assert 'data = glob(["**"]),' in dependency_content
