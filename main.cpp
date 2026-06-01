#include <string>
#include <vector>
#include <iostream>

int main() {
    std::cout << "Welcome to Viper executable. select a function to get started:\n";
    std::string command;
    std::cout << "[1] Compile\n";
    std::cout << "[2] Interpret\n";
    std::cout << "\n";
    std::cout << "Viper> ";
    std::getline(std::cin, command);
    std::cout << command << " Either doesnt exist or is a stub" << std::endl;
}
