/* epdbb.c - fast bit-bang SPI for the Waveshare e-paper on the Odroid C2.
 *
 * The pure-Python bit-bang pays ~50 us per GPIO write through the wiringPi SWIG
 * binding, so a full 800x480 two-plane transfer takes ~2 minutes. Moving the
 * inner loop into C (memory-mapped GPIO via Hardkernel wiringPi) drops a write
 * to tens of nanoseconds, so the same transfer takes ~1-2 s.
 *
 * Build:  gcc -O3 -fPIC -shared native/epdbb.c -o native/libepdbb.so -lwiringPi
 *
 * Python loads this with ctypes (see epaper/display/gpio.py: NativeGPIO).
 */
#include <wiringPi.h>

/* This Hardkernel source tree references these two GPIO map pointers from the
 * board files but doesn't define storage for them in the core we link. The C2
 * board init (init_odroidc2) assigns them at setup; we just provide the symbol.
 */
const int *pinToGpio = 0;
const int *phyToGpio = 0;

static int DIN, CLK, CS, DC;
static volatile int g_delay = 0;   /* clock half-period: empty-loop iterations */

static inline void clkdelay(void) {
    volatile int i;
    for (i = 0; i < g_delay; i++) { }
}

int  epd_setup(void)        { return wiringPiSetupPhys(); }
void epd_set_delay(int d)   { g_delay = d; }
void epd_mode_out(int pin)  { pinMode(pin, OUTPUT); }
void epd_mode_in(int pin)   { pinMode(pin, INPUT); }
void epd_write(int pin, int v) { digitalWrite(pin, v); }
int  epd_read(int pin)      { return digitalRead(pin); }

/* Pins used by the bulk transfer (data lines). CS/DC are toggled here. */
void epd_set_spi_pins(int din, int clk, int cs, int dc) {
    DIN = din; CLK = clk; CS = cs; DC = dc;
}

static inline void shift_byte(unsigned char b) {
    int k;
    for (k = 7; k >= 0; k--) {
        digitalWrite(DIN, (b >> k) & 1);
        digitalWrite(CLK, 1); clkdelay();
        digitalWrite(CLK, 0); clkdelay();
    }
}

/* Send a contiguous data block (DC=1). invert!=0 XORs each byte (red plane). */
void epd_block(const unsigned char *buf, int len, int invert) {
    int i;
    unsigned char m = invert ? 0xFF : 0x00;
    digitalWrite(DC, 1);
    digitalWrite(CS, 0);
    for (i = 0; i < len; i++)
        shift_byte(buf[i] ^ m);
    digitalWrite(CS, 1);
}
