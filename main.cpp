#include <string>
#include <vector>
#include <iostream>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cout << "Usage: 'viper compile/interp'";
        return 1;
    }
    if (std::string(argv[1]) == "compile") {
        std::cout << "Compile is currently a stub";
    } else if (std::string(argv[1]) == "interp") {
        std::cout << "Interp is currently a stub";
    }
}
