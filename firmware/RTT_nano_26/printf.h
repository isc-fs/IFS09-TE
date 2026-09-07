/*
 * printf.h — Serial stdout redirect for Arduino AVR (used by RF24 printDetails)
 */

#ifndef RF24_PRINTF_H_
#define RF24_PRINTF_H_

#if defined(ARDUINO_ARCH_AVR) || defined(__ARDUINO_X86__) || defined(ARDUINO_ARCH_MEGAAVR)

int serial_putc(char c, FILE*)
{
    Serial.write(c);
    return c;
}

#elif defined(ARDUINO_ARCH_MBED)
REDIRECT_STDOUT_TO(Serial);

#endif

void printf_begin(void)
{
#if defined(ARDUINO_ARCH_AVR) || defined(ARDUINO_ARCH_MEGAAVR)
    fdevopen(&serial_putc, 0);

#elif defined(__ARDUINO_X86__)
    stdout = freopen("/dev/ttyGS0", "w", stdout);
    delay(500);
    printf("Redirecting to Serial...");
#endif
}

#endif // RF24_PRINTF_H_
