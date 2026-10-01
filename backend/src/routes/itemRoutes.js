import express from 'express';
import {
  getItems,
  createItem,
  toggleItem,
  deleteItem,
} from '../controllers/itemController.js';

const router = express.Router();

router.route('/')
  .get(getItems)
  .post(createItem);

router.route('/:id')
  .delete(deleteItem);

router.route('/:id/toggle')
  .patch(toggleItem);

export default router;
