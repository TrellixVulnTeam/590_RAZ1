from resnet import ResNet_  as Net
from cutout  import Cutout
import numpy as np
import argparse
import os, sys
import time
import datetime
from copy import deepcopy
# Import pytorch dependencies
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
import torchvision.transforms as transforms
import torch.optim as optim
from torch.optim.lr_scheduler import MultiStepLR

def get_num_correct(pred,labels):
    return pred.argmax(dim=1).eq(labels).sum().item()
def init_weights(m):
    if type(m)==nn.Linear or type(m)==nn.Conv2d:
        torch.nn.init.xavier_uniform_(m.weight)
        
device = 'cuda' if torch.cuda.is_available() else 'cpu'

def train_(train_set,test_set,lr, depth, mixup_enbale, alpha, model_checkpoint,epochs):

    torch.manual_seed(1)
    train_loader=torch.utils.data.DataLoader(train_set, batch_size=128, shuffle=False, pin_memory=True,num_workers=2)
    test_loader=torch.utils.data.DataLoader(test_set, batch_size=100, shuffle=False, pin_memory=True,num_workers=2)
    network= Net(depth).to(device)
    optimizer = optim.SGD(network.parameters(), lr=lr, momentum=0.9, nesterov=True, weight_decay=5e-4)
    criterion = torch.nn.CrossEntropyLoss().to(device)
#     scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.95)
    scheduler = MultiStepLR(optimizer, milestones=[30, 60, 80], gamma=0.2)
    
    acc_train=[]
    acc_test=[]
    acc = 0
    best_acc = 0
    for epoch in range(epochs):
        total_loss = 0
        total_correct = 0
        network.train()
        count_in = 0
        for batch in train_loader: #Get batch
            images,labels = batch
            images, labels = images.to(device), labels.to(device)
            
            if mixup_enbale:
                images, targets_a, targets_b, lam = mixup_data(images, labels, alpha)
                images, targets_a, targets_b = map(Variable, (images,
                                                          targets_a, targets_b))
                preds = network(images)
                loss = mixup_criterion(criterion, preds, targets_a, targets_b, lam)

                _, predicted = torch.max(preds.data, 1)
                correct = (lam * predicted.eq(targets_a.data).cpu().sum().float()
                + (1 - lam) * predicted.eq(targets_b.data).cpu().sum().float())
                total_correct += correct
            
            if not mixup_enbale:
                preds=network(images) #pass batch to network
                correct = get_num_correct(preds, labels)
                loss = criterion(preds,labels) #Calculate loss
                total_correct+=correct
            
            optimizer.zero_grad()
            loss.backward() #Calculate gradients
            optimizer.step() #Update weights
            
            
        print("epoch: ", epoch,  "total_correct: ", total_correct.item() )
        print("training accuracy: ", total_correct.item() /len(train_set))
        acc_train.append(deepcopy(float(total_correct)/len(train_set)))

        with torch.no_grad():
            correct_test=0
            for batch_test in test_loader: #Get batch
                
                images_test,labels_test = batch_test
                images_test, labels_test = images_test.to(device), labels_test.to(device)
                preds_test=network(images_test) #pass batch to network
                correct_test += get_num_correct(preds_test, labels_test)
                
            print("testing accuracy: ", correct_test / len(test_set))
            if epoch == epochs - 1:
                print(correct_test / len(test_set))
                acc = correct_test / len(test_set) 
            acc_test.append(deepcopy(float(correct_test)/len(test_set)))
        scheduler.step()
        if best_acc < acc:
            best_acc = acc
            torch.save(network.state_dict(), model_checkpoint)

    return (acc_train,acc_test)
    
def do_test(flag_augmetation = False, 
            flag_cutout = False, 
            n_holes = 1, 
            length = 16, 
            depth = 18,
            epochs = 100,
            lr = 0.1,
            mixup_enbale = True,
            alpha = 0.1
           ):
    model_checkpoint = "resnet" + str(depth) 
    if flag_augmetation:
        model_checkpoint += '+'
    if flag_cutout:
        model_checkpoint += "cutout"
    model_checkpoint += ".pt"
    
    normalize = transforms.Normalize(mean=[x / 255.0 for x in [125.3, 123.0, 113.9]],
                                     std=[x / 255.0 for x in [63.0, 62.1, 66.7]])

    train_transform = transforms.Compose([])
    if flag_augmetation:
        train_transform.transforms.append(transforms.RandomCrop(32, padding=4))
        train_transform.transforms.append(transforms.RandomHorizontalFlip())
    train_transform.transforms.append(transforms.ToTensor())
    train_transform.transforms.append(normalize)
    if flag_cutout:
        train_transform.transforms.append(Cutout(n_holes = n_holes, length = length))


    train_set=torchvision.datasets.CIFAR10(
        root='./data/cifar10',
        train=True,
        download=True,
        transform=train_transform)

    test_set=torchvision.datasets.CIFAR10(
        root='./data/cifar10',
        train=False,
        download=True,
        transform=transforms.Compose([transforms.ToTensor(), normalize]))
    
    acc_train,acc_test = train_(train_set,test_set,lr, depth,mixup_enbale,alpha,  model_checkpoint, epochs = epochs)
    return (acc_train,acc_test)


list_acc = []
for depth in [18,34,50]:
    acc_train,acc_test  =do_test(flag_augmetation = True, 
                                flag_cutout = False, 
                                n_holes = 1, 
                                length = 16, 
                                depth = depth,
                                epochs = 100,
                                lr = 0.02,
                                mixup_enbale = False,
                                alpha = 0.1)
    list_acc.append(acc_train)
    list_acc.append(acc_test)

        
import pandas as pd
list_acc = pd.DataFrame(list_acc)
list_acc.to_csv("acc_base.csv",index = False)

list_acc = []
for depth in [18,34,50]:
    acc_train,acc_test  =do_test(flag_augmetation = True, 
                                flag_cutout = True, 
                                n_holes = 1, 
                                length = 16, 
                                depth = depth,
                                epochs = 100,
                                lr = 0.02,
                                mixup_enbale = False,
                                alpha = 0.1)
    list_acc.append(acc_train)
    list_acc.append(acc_test)

        
import pandas as pd
list_acc = pd.DataFrame(list_acc)
list_acc.to_csv("acc_cutout.csv",index = False)

print(list_acc)

list_acc = []
for depth in [18,34,50]:
    acc_train,acc_test  =do_test(flag_augmetation = True, 
                                flag_cutout = False, 
                                n_holes = 1, 
                                length = 16, 
                                depth = depth,
                                epochs = 100,
                                lr = 0.02,
                                mixup_enbale = True,
                                alpha = 0.1)
    list_acc.append(acc_train)
    list_acc.append(acc_test)

        
import pandas as pd
list_acc = pd.DataFrame(list_acc)
list_acc.to_csv("acc_mixup.csv",index = False)

print(list_acc)