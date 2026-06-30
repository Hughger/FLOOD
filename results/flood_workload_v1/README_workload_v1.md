# FLOOD workload v1 summary

Representative proxy shapes for SD UNet, VAE Decoder, and DiT. These are not yet full model traces.

- unet_conv_64_320_320: baseline 187707 cycles, FLOOD estimate 155357 cycles, speedup 1.208x.
- unet_conv_32_640_640: baseline 136456 cycles, FLOOD estimate 112942 cycles, speedup 1.208x.
- unet_conv_16_1280_1280: baseline 294253 cycles, FLOOD estimate 243536 cycles, speedup 1.208x.
- attn_qkv_4096_320_320: baseline 34810 cycles, FLOOD estimate 27527 cycles, speedup 1.265x.
- attn_score_1024_64_1024: baseline 13070 cycles, FLOOD estimate 10341 cycles, speedup 1.264x.
- attn_softmax_1024_1024: baseline 43587 cycles, FLOOD estimate 30774 cycles, speedup 1.416x.
- vae_dec_conv_64_256_128: baseline 47318 cycles, FLOOD estimate 39170 cycles, speedup 1.208x.
- dit_qkv_256_768_768: baseline 10941 cycles, FLOOD estimate 8658 cycles, speedup 1.264x.
- dit_mlp_256_768_3072: baseline 36396 cycles, FLOOD estimate 28781 cycles, speedup 1.265x.
- dit_softmax_256_256: baseline 4602 cycles, FLOOD estimate 3258 cycles, speedup 1.413x.
