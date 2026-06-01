#include <string>
#include <vector>
#include <iostream>

int main() {
    std::cout << "Welcome to Viper executable. select a function to get started:\n";
    int command;
    std::cout << "[1] Compile\n";
    std::cout << "[2] Interpret\n";
    std::cout << "\n";
    std::cout << "Viper> ";
    std::cin >> command;
    if (command == 1) {
        std::cout << "\n" << "Viper compiler" << "\n";
        std::cout << "Stub";
        return 1;
    } else if (command == 2) {
        std::cout << "\n" << "Interpreter" << "\n";
        std::cout << "Stub";
        return 1;
    } else {
        std::cout << "\n";
        std::cout << "Not a function";
        return 2;
    }
}
