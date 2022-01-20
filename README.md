# End-to-End Trainable Multi-Instance Pose Estimation with Transformers

# POET
Implementation of POET for pose estimation
<!-- ![alt text](https://raw.githubusercontent.com/HHTseng/video-classification/master/fig/CRNN.png) -->

# Getting Started
## Prerequisites
* PyTorch 
* Python 3


### COCO Dataset

```
+ data 
    + annotations   
    + train2017 
```


## Train
Once you have downloaded the dataset, start training ->
```
python -m torch.distributed.launch --nproc_per_node=2 --use_env main.py --coco_path ./data/ --batch_size 4 --pretrained ./detr-r50-e632da11.pth
```



## Inference
```
python inference.py
```

## References
* https://arxiv.org/pdf/2103.12115.pdf
* https://github.com/facebookresearch/detr

## License
This project is licensed under the Apache License 

