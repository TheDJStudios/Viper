#include <string>
#include <vector>
#include <iostream>

int main(int argc, char* argv[]) {
    std::string mode = argv[1];
    if (argc < 2) {
        std::cout << "Usage: 'viper compile/interp'\n";
        return 1;
    }
    if (mode == "compile") {
        std::cout << "Compile is currently a stub\n";
    } else if (mode == "interp") {
        std::cout << "Interp is currently a stub\n";
    }
}
