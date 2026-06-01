cmake_minimum_required(VERSION 4.2)
project(Viper)

set(CMAKE_CXX_STANDARD 14)

include_directories(Viper_compiler)
include_directories(Viper_interpreter)

add_executable(Viper
        Viper_compiler/main.cpp
        "Viper_interpreter/Python viper/main.py"
        "Viper_interpreter/Viper/main old.py"
        Viper_interpreter/Viper/main.py)
