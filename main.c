#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

static int vp_argc = 0;
static char **vp_argv = NULL;

static void vp_print_int(long long value) { printf("%lld\n", value); }
static void vp_print_double(double value) { printf("%g\n", value); }
static void vp_print_bool(bool value) { puts(value ? "true" : "false"); }
static void vp_print_str(const char *value) { puts(value == NULL ? "" : value); }
static void vp_print_char(char value) { printf("%c\n", value); }
static void vp_print_none(void *value) { (void)value; puts("none"); }

static long long importedValue(void);
static void showImportedMessage(void);
static long long localValue(void);

static long long importedValue(void) {
    return (6 * 7);
}

static void showImportedMessage(void) {
    vp_print_str("from secondary.vp");
    return;
}

static long long localValue(void) {
    return (4 * 5);
}

int main(int argc, char **argv) {
    vp_argc = argc > 1 ? argc - 1 : 0;
    vp_argv = argc > 1 ? argv + 1 : argv;
    long long number = (5 * 3);
    bool ready = true;
    void * missing = NULL;
    vp_print_str("Viper file successfully ran");
    vp_print_int(number);
    vp_print_int((2 + (3 * 4)));
    vp_print_int(((2 + 3) * 4));
    vp_print_none(missing);
    vp_print_int(localValue());
    vp_print_int(importedValue());
    showImportedMessage();
    if ((ready && (number == 15))) {
        vp_print_str("if branch");
    }
    else if ((number > 20)) {
        vp_print_str("else if branch");
    }
    else {
        vp_print_str("else branch");
    }
    if ((ready && (number == 10))) {
        vp_print_str("Testing the new jetbrains plugin");
    }
    else {
        vp_print_str("Failed to meet conditions");
    }
    return 0;
}
