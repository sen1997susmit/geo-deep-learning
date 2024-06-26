import torch
import torch.nn as nn
import torch.nn.functional as F


def soft_dice_score(
        output: torch.Tensor, target: torch.Tensor, smooth: float = 0.0, eps: float = 1e-7, dims=None) -> torch.Tensor:
    assert output.size() == target.size()
    if dims is not None:
        intersection = torch.sum(output * target, dim=dims)
        cardinality = torch.sum(output + target, dim=dims)
        # print('cardinality', cardinality, 'intersection', intersection)
    else:
        intersection = torch.sum(output * target)
        cardinality = torch.sum(output + target)
    dice_score = (2.0 * intersection + smooth) / (cardinality + smooth).clamp_min(eps)
    # print('dice_score', dice_score)
    return dice_score


class DiceLoss(nn.Module):
    """Implementation of Dice loss for image segmentation task from 
    https://smp.readthedocs.io/en/latest/losses.html#diceloss.
    It supports binary and multiclass cases.
    """

    def __init__(self, smooth=1.0, eps=1e-7, ignore_index=None, mode='MULTICLASS_MODE'):
        """Initialize the dice loss for image segmentation task.

        Args:
            smooth (float, optional): smoothness constant for dice coefficient . Defaults to 1.0.
            eps (float, optional): small epsilon for numerical stability to avoid zero division error. Defaults to 1e-7.
            ignore_index (int, optional): target value that is ignored and does not contribute to the input gradient. Defaults to None.
            mode (str, optional): loss mode 'MULTICLASS_MODE' or 'BINARY_MODE'. Defaults to 'MULTICLASS_MODE'.
        """     
        super().__init__()
        self.smooth = smooth
        self.eps = eps
        self.ignore_index = ignore_index
        self.mode = mode

    def forward(self, output, target):
        """Foward function use during trainning. 
        
        Args:
            output (Tensor): the output from model.
            target (Tensor): ground truth.

        Returns:
            Tensor: dice loss score.
        """        
        bs = target.size(0)
        num_classes = output.size(1)
        dims = (0, 2)
        # print(self.mode, self.ignore_index)

        if self.mode == 'MULTICLASS_MODE':
            output = output.log_softmax(dim=1).exp()
        else:
            output = F.logsigmoid(output).exp()
        # output = output.log_softmax(dim=1).exp()

        if self.mode == 'BINARY_MODE':
            target = target.view(bs, 1, -1)
            output = output.view(bs, 1, -1)

            if self.ignore_index is not None:
                mask = target != self.ignore_index
                output = output * mask
                target = target * mask
        else:
            target = target.view(bs, -1)
            output = output.view(bs, num_classes, -1)
            if self.ignore_index is not None:
                mask = target != self.ignore_index
                output = output * mask.unsqueeze(1)

                target = F.one_hot((target * mask).to(torch.long), num_classes)  # N,H*W -> N,H*W, C
                target = target.permute(0, 2, 1) * mask.unsqueeze(1)

            else:
                target = F.one_hot(target, num_classes)  # N,H*W -> N,H*W, C
                target = target.permute(0, 2, 1)  # H, C, H*W

        scores = soft_dice_score(output, target.type_as(output), smooth=self.smooth, eps=self.eps, dims=dims)
        loss = 1.0 - scores

        mask = target.sum(dims) > 0
        loss *= mask.to(loss.dtype)

        return loss.mean()
