ENTRY(_start)
SECTIONS
{
    . = 0;
    .text : { *(.text*) }
    . = ALIGN(16);
    .data : { *(.data*) *(.sdata*) *(.rodata*) *(.srodata*) }
    .bss : { *(.bss*) *(.sbss*) }
}
