from conans import ConanFile
from conans import tools
import os


class BoostConan(ConanFile):
    name = "Boost"
    version = "1.62.0"
    digest = "440a59f8bc4023dbe6285c9998b0f7fa288468b889746b1ef00e8b36c559dce1"
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "header_only": [True, False], "fPIC": [True, False]}
    default_options = "shared=False", "header_only=False", "fPIC=False"
    url = "https://github.com/lasote/conan-boost"
    exports = ["FindBoost.cmake"]
    license = "Boost Software License - Version 1.0. http://www.boost.org/LICENSE_1_0.txt"

    def __init__(self, *args, **kw):
        super(BoostConan, self).__init__(*args, **kw)

    @property
    def folder_name(self):
        name = "boost_%s" % self.version.replace(".", "_")
        # strip the beta version because the folder extracted from the archive
        # doesn't have it
        if "beta" in self.version:
            ix = name.find("_beta_")
            name = name[:ix]
        return name

    @property
    def archive_name(self):
        if "beta" in self.version:
            name = self.version.replace(".", "_").replace("beta_", "b")
        else:
            name = self.version.replace(".", "_")
        return "boost_%s.tar.gz" % name

    def conan_info(self):
        if self.options.header_only:
            self.info.requires._data = {}

    def config_options(self):
        if self.settings.compiler == "Visual Studio" and \
           self.options.shared and "MT" in str(self.settings.compiler.runtime):
            self.options.shared = False

        if self.settings.compiler == "Visual Studio":
            try:
                self.options.remove("fPIC")
            except:
                pass

        # Header only
        if self.options.header_only:
            self.settings.remove("compiler")
            self.settings.remove("os")
            self.settings.remove("arch")
            self.settings.remove("build_type")
            self.options.remove("shared")

    def configure(self):
        # BZIP2
        if self.settings.os == "Linux" or self.settings.os == "Macos":
            self.requires.add("bzip2/1.0.6@lasote/stable", private=False)
            if not self.options.header_only:
                self.options["bzip2/1.0.6"].shared = self.options.shared
        self.requires.add("zlib/1.2.8@lasote/stable", private=False)

        if "zlib" in self.requires:
            if not self.options.header_only:
                self.options["zlib"].shared = self.options.shared

        if "bzip2" in self.requires:
            if not self.options.header_only:
                self.options["bzip2"].shared = self.options.shared

    def source(self):
        zip_name = self.archive_name
        url = "http://sourceforge.net/projects/boost/files/boost/{version}/{archive}/download"
        url = url.format(version=self.version, archive=zip_name)

        self.output.info("Downloading %s..." % url)
        tools.download(url, zip_name)
        tools.check_sha256(zip_name, self.digest)
        tools.unzip(zip_name, ".")
        os.unlink(zip_name)

    def build(self):
        if self.options.header_only:
            self.output.warn("Header only package, skipping build")
            return

        command = "bootstrap" if self.settings.os == "Windows" else "./bootstrap.sh"
        if self.settings.os == "Windows" and self.settings.compiler == "gcc":
            command += " mingw"
        try:
            self.run("cd %s && %s" % (self.folder_name, command))
        except:
            self.run("cd %s && type bootstrap.log" % self.folder_name
                     if self.settings.os == "Windows"
                     else "cd %s && cat bootstrap.log" % self.folder_name)
            raise

        flags = []
        if self.settings.compiler == "Visual Studio":
            flags.append("toolset=msvc-%s.0" % self.settings.compiler.version)
        elif str(self.settings.compiler) in ["clang", "gcc"]:
            flags.append("toolset=%s" % self.settings.compiler)

        flags.append("link=%s" % ("static" if not self.options.shared else "shared"))
        if self.settings.compiler == "Visual Studio" and self.settings.compiler.runtime:
            flags.append("runtime-link=%s" % ("static" if "MT" in str(self.settings.compiler.runtime) else "shared"))
        flags.append("variant=%s" % str(self.settings.build_type).lower())
        flags.append("address-model=%s" % ("32" if self.settings.arch == "x86" else "64"))

        cxx_flags = []
        # fPIC DEFINITION
        if self.settings.compiler != "Visual Studio":
            if self.options.fPIC:
                cxx_flags.append("-fPIC")

        # LIBCXX DEFINITION FOR BOOST B2
        try:
            if str(self.settings.compiler.libcxx) == "libstdc++":
                flags.append("define=_GLIBCXX_USE_CXX11_ABI=0")
            elif str(self.settings.compiler.libcxx) == "libstdc++11":
                flags.append("define=_GLIBCXX_USE_CXX11_ABI=1")
            if "clang" in str(self.settings.compiler):
                if str(self.settings.compiler.libcxx) == "libc++":
                    cxx_flags.append("-stdlib=libc++")
                    cxx_flags.append("-std=c++11")
                    flags.append('linkflags="-stdlib=libc++"')
                else:
                    cxx_flags.append("-stdlib=libstdc++")
                    cxx_flags.append("-std=c++11")
        except:
            pass

        cxx_flags = 'cxxflags="%s"' % " ".join(cxx_flags) if cxx_flags else ""
        flags.append(cxx_flags)

        # JOIN ALL FLAGS
        b2_flags = " ".join(flags)

        command = "b2" if self.settings.os == "Windows" else "./b2"
        if self.settings.os == "Linux":
            deps_options = self.prepare_deps_options()
        else:
            deps_options = ""

        full_command = "cd %s && %s %s -j4 --abbreviate-paths --without-python %s" % (
            self.folder_name, command, b2_flags, deps_options)
        self.output.warn(full_command)
        self.run(full_command)  # , output=False)

    def prepare_deps_options(self):
        ret = ""
#        if "bzip2" in self.requires:
#            include_path = self.deps_cpp_info["bzip2"].include_paths[0]
#            lib_path = self.deps_cpp_info["bzip2"].lib_paths[0]
#            lib_name = self.deps_cpp_info["bzip2"].libs[0]
#            ret += "-s BZIP2_BINARY=%s -s BZIP2_INCLUDE=%s -s BZIP2_LIBPATH=%s" % (lib_name, include_path, lib_path)
#    FIXME: I think ZLIB variables should be setted now as env variables. But compilation works anyway.
#         if "zlib" in self.requires:
#             include_path = self.deps_cpp_info["zlib"].include_paths[0]
#             lib_path = self.deps_cpp_info["zlib"].lib_paths[0]
#             lib_name = self.deps_cpp_info["zlib"].libs[0]
#             ret += "-s ZLIB_BINARY=%s -s ZLIB_INCLUDE=%s -s ZLIB_LIBPATH=%s" % (lib_name, include_path, lib_path)

        return ret

    def package(self):
        # Copy findZLIB.cmake to package
        self.copy("FindBoost.cmake", ".", ".")

        self.copy(pattern="*", dst="include/boost", src="%s/boost" % self.folder_name)
        self.copy(pattern="*.a", dst="lib", src="%s/stage/lib" % self.folder_name)
        self.copy(pattern="*.so", dst="lib", src="%s/stage/lib" % self.folder_name)
        self.copy(pattern="*.so.*", dst="lib", src="%s/stage/lib" % self.folder_name)
        self.copy(pattern="*.dylib*", dst="lib", src="%s/stage/lib" % self.folder_name)
        self.copy(pattern="*.lib", dst="lib", src="%s/stage/lib" % self.folder_name)
        self.copy(pattern="*.dll", dst="bin", src="%s/stage/lib" % self.folder_name)

    def package_info(self):

        if not self.options.header_only and self.options.shared:
            self.cpp_info.defines.append("BOOST_ALL_DYN_LINK")
        else:
            self.cpp_info.defines.append("BOOST_USE_STATIC_LIBS")

        if self.options.header_only:
            return

        libs = (
            "unit_test_framework",
            "prg_exec_monitor",
            "test_exec_monitor",
            "atomic",
            "container",
            "date_time",
            "exception",
            "filesystem",
            "graph",
            "iostreams",
            "locale",
            "log_setup",
            "log",
            "math_c99",
            "math_c99f",
            "math_c99l",
            "math_tr1",
            "math_tr1f",
            "math_tr1l",
            "program_options",
            "random",
            "regex",
            "wserialization",
            "serialization",
            "signals",
            "coroutine",
            "fiber",
            "context",
            "wave",
            "timer",
            "thread",
            "chrono",
            "system",
            "type_erasure",
        )

        if self.settings.compiler != "Visual Studio":
            self.cpp_info.libs.extend(["boost_%s" % lib for lib in libs])
        else:
            win_libs = []
            # http://www.boost.org/doc/libs/1_55_0/more/getting_started/windows.html
            visual_version = int(str(self.settings.compiler.version)) * 10
            runtime = "mt"  # str(self.settings.compiler.runtime).lower()

            abi_tags = []
            if self.settings.compiler.runtime in ("MTd", "MT"):
                abi_tags.append("s")

            if self.settings.build_type == "Debug":
                abi_tags.append("gd")

            abi_tags = ("-%s" % "".join(abi_tags)) if abi_tags else ""

            version = "_".join(self.version.split(".")[0:2])
            suffix = "vc%d-%s%s-%s" % (visual_version, runtime, abi_tags, version)
            prefix = "lib" if not self.options.shared else ""

            win_libs.extend(["%sboost_%s-%s" % (prefix, lib, suffix)
                             for lib in libs if lib not in ["exception", "test_exec_monitor"]])
            win_libs.extend(["libboost_exception-%s" % suffix, "libboost_test_exec_monitor-%s" % suffix])

            # self.output.warn("EXPORTED BOOST LIBRARIES: %s" % win_libs)
            self.cpp_info.libs.extend(win_libs)
            # DISABLES AUTO LINKING! NO SMART AND MAGIC DECISIONS THANKS!
            self.cpp_info.defines.extend(["BOOST_ALL_NO_LIB"])
